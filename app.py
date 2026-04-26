#!/usr/bin/env python3
"""
Ningen AI Boardroom
Run: streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

# ── Start Flask API server (once, cached across reruns) ─────────
import threading, time, socket

def _api_port_open(port=5001):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
        s.close()
        return True
    except OSError:
        return False

@st.cache_resource
def _ensure_api_running():
    if _api_port_open():
        return "already_running"
    from api_server import start_server
    t = threading.Thread(target=start_server, args=(5001,), daemon=False)
    t.start()
    for _ in range(20):
        time.sleep(0.5)
        if _api_port_open():
            return "started"
    return "timeout"

_ensure_api_running()

# ── Page config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Ningen — AI Boardroom",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { display: none !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.stApp { padding: 0 !important; margin: 0 !important; background: #D4A882; }
.block-container { padding: 0 !important; max-width: 100% !important; }
</style>
""", unsafe_allow_html=True)


# ── Patch uidesign.html to use real backend ─────────────────────
def load_ui():
    html_path = Path("uidesign.html")
    if not html_path.exists():
        st.error("uidesign.html not found!")
        return ""

    html = html_path.read_text(encoding="utf-8")

    # ── 1. Replace startMeeting() — show intro message, wait for user input
    old_start = """  const startMeeting = () => {
    clearSim();
    setTab(0);
    setTimeout(() => {
      setSimState('running');
      setEpisode({current:1,total:3,trend:0});
      runMsg(0, {Requirements:0,Product:0,Marketing:0,Conflicts:0,Efficiency:0}, 0, new Set());
    }, 60);
  };"""

    new_start = """  const startMeeting = () => {
    clearSim();
    setTab(0);
    setSimState('running');
    setMessages([{agent:'SYSTEM', round:'INTRO', text:'Welcome to the Ningen AI Boardroom! What product or startup idea should we build today?'}]);
    setInputGlow(true);
    window._ningenPhase = 'idle';
    fetch('http://localhost:5001/api/reset', {method:'POST'}).catch(()=>{});
  };"""

    # ── 2. Replace handleSend() — send to Flask API, keep local optimistic update
    old_send = """  const handleSend = () => {
    if (!input.trim()) return;
    setMessages(prev => [...prev, {agent:'FOUNDER',round:'REPLY',text:input.trim()}]);
    setInput(''); setInputGlow(false);
  };"""

    new_send = """  const handleSend = () => {
    if (!input.trim()) return;
    const text = input.trim();
    setMessages(prev => [...prev, {agent:'FOUNDER', round:'REPLY', text}]);
    setInput('');
    setInputGlow(false);
    const phase = window._ningenPhase || 'idle';
    fetch('http://localhost:5001/api/send', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, phase})
    }).catch(()=>{});
    window._ningenPhase = 'waiting';
  };

  // ── Poll backend every 1.5s for real board meeting messages + agent results ──
  useEffect(() => {
    const iv = setInterval(() => {
      fetch('http://localhost:5001/api/messages')
        .then(r => r.json())
        .then(data => {
          if (data.messages && data.messages.length > 0) setMessages(data.messages);
          if (data.agentStates)          setAgentState(data.agentStates);
          if (data.statuses)             setStatuses(data.statuses);
          if (data.scores)               setScores(data.scores);
          if (data.reward !== undefined) setReward(data.reward);
          if (data.episode)              setEpisode(data.episode);
          if (data.agent_results)        setAgentResults(data.agent_results);
          if (data.phase) {
            window._ningenPhase = data.phase;
            if (data.phase === 'answering') setInputGlow(true);
            if (data.phase === 'done')      { setSimState('done'); setInputGlow(false); }
          }
        })
        .catch(()=>{});
    }, 1500);
    return () => clearInterval(iv);
  }, []);"""

    # ── 3. Add agentResults + modal state after episode state ────────
    html = html.replace(
        "  const [episode, setEpisode]     = useState({current:0,total:3,trend:0});",
        "  const [episode, setEpisode]     = useState({current:0,total:3,trend:0});\n"
        "  const [agentResults, setAgentResults] = useState("
        "{CEO:{status:'idle',output:''},CTO:{status:'idle',output:''},"
        "CMO:{status:'idle',output:''},COO:{status:'idle',output:''}});\n"
        "  const [modal, setModal] = useState(null);",
    )

    # ── 4. Replace play area with clickable live Results box ─────────
    results_box = r"""<Room label="results" labelPos="c" style={{flex:1,overflow:'hidden'}}>
            <div style={{display:'flex',flexDirection:'column',gap:5,padding:'6px 8px',height:'100%',justifyContent:'center'}}>
              {[
                {id:'CTO',label:'Building',  color:'#3B5EA6'},
                {id:'CMO',label:'Marketing', color:'#D93025'},
                {id:'COO',label:'Planning',  color:'#4A9B6A'},
                {id:'CEO',label:'Strategy',  color:'#E8C84A'},
              ].map(({id,label,color}) => {
                const r = agentResults[id] || {status:'idle',output:''};
                const isDone = r.status === 'done';
                const sColor = {idle:'#bbb',running:'#F5A04A',done:'#27AE60',error:'#E74C3C'}[r.status]||'#bbb';
                const sLabel = {idle:'waiting',running:label+'...',done:'tap to view',error:'✗ error'}[r.status]||'waiting';
                const handleClick = () => {
                  if (!isDone) return;
                  fetch(`http://localhost:5001/api/output/${id}`)
                    .then(res => res.json())
                    .then(data => setModal({agent:id, color, ...data}))
                    .catch(()=>{});
                };
                return (
                  <div key={id} onClick={handleClick}
                    style={{display:'flex',alignItems:'center',gap:7,padding:'5px 7px',
                    borderRadius:8,border:`1.5px solid ${color}${isDone?'99':'33'}`,
                    background:`${color}${isDone?'18':'0D'}`,
                    cursor:isDone?'pointer':'default',
                    transition:'all 0.2s',
                    boxShadow:isDone?`0 2px 8px ${color}33`:'none'}}>
                    <div style={{width:22,height:22,borderRadius:'50%',overflow:'hidden',flexShrink:0,
                      border:`2px solid ${color}`,boxShadow:r.status==='running'?`0 0 6px ${color}88`:'none'}}>
                      <img src={window.IMGS[id]} style={{width:'100%',height:'100%',objectFit:'cover'}} />
                    </div>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{fontSize:9,fontWeight:700,color:'#333',letterSpacing:0.3}}>{id}</div>
                      <div style={{fontSize:8,color:sColor,fontWeight:600,
                        animation:r.status==='running'?'statusBlink 1s infinite':'none'}}>{sLabel}</div>
                    </div>
                    {r.status==='running' && (
                      <div style={{width:6,height:6,borderRadius:'50%',background:'#F5A04A',
                        animation:'pulse 1s infinite',flexShrink:0}} />
                    )}
                    {isDone && <span style={{fontSize:10,color:color,flexShrink:0}}>›</span>}
                  </div>
                );
              })}
            </div>
          </Room>"""

    html = html.replace(
        '<Room label="play area" labelPos="c" style={{flex:1}} />',
        results_box,
    )

    # ── 5. Inject modal component just before closing </div> of App return ──
    modal_jsx = r"""
    {modal && (
      <div onClick={()=>setModal(null)} style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.75)',
        zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
        <div onClick={e=>e.stopPropagation()} style={{background:'#fff',borderRadius:16,
          width:'90vw',height:'88vh',display:'flex',flexDirection:'column',overflow:'hidden',
          border:`3px solid ${modal.color||'#333'}`}}>

          {/* Modal header */}
          <div style={{display:'flex',alignItems:'center',gap:12,padding:'12px 18px',
            borderBottom:'2px solid #eee',background:'#fafafa',flexShrink:0}}>
            <div style={{width:32,height:32,borderRadius:'50%',overflow:'hidden',
              border:`2px solid ${modal.color}`}}>
              <img src={window.IMGS[modal.agent]} style={{width:'100%',height:'100%',objectFit:'cover'}} />
            </div>
            <span style={{fontWeight:800,fontSize:15,color:'#111'}}>{modal.agent} Output</span>
            <button onClick={()=>setModal(null)}
              style={{marginLeft:'auto',background:'none',border:'2px solid #ccc',borderRadius:8,
                padding:'4px 12px',cursor:'pointer',fontWeight:700,fontSize:13}}>✕ Close</button>
          </div>

          {/* CTO — render HTML in iframe */}
          {modal.type === 'html' && (
            <iframe srcDoc={modal.content} style={{flex:1,border:'none',width:'100%'}}
              title="Product Preview" sandbox="allow-scripts allow-same-origin" />
          )}

          {/* CMO / COO / CEO — tabbed text content */}
          {(modal.type === 'cmo' || modal.type === 'doc') && modal.files && (() => {
            const keys = Object.keys(modal.files);
            const [activeTab, setActiveTab] = React.useState(keys[0]);
            return (
              <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden'}}>
                <div style={{display:'flex',gap:8,padding:'10px 16px',borderBottom:'2px solid #eee',
                  flexShrink:0,overflowX:'auto'}}>
                  {keys.map(k => (
                    <button key={k} onClick={()=>setActiveTab(k)}
                      style={{padding:'6px 14px',borderRadius:20,border:`2px solid ${modal.color}`,
                        background:activeTab===k?modal.color:'transparent',
                        color:activeTab===k?'#fff':modal.color,
                        fontWeight:700,fontSize:12,cursor:'pointer',whiteSpace:'nowrap'}}>
                      {k}
                    </button>
                  ))}
                </div>
                <pre style={{flex:1,overflow:'auto',margin:0,padding:'16px 20px',
                  fontSize:13,lineHeight:1.6,whiteSpace:'pre-wrap',wordBreak:'break-word',
                  fontFamily:'system-ui,sans-serif',color:'#222',background:'#fdfdfd'}}>
                  {modal.files[activeTab] || '(empty)'}
                </pre>
              </div>
            );
          })()}
        </div>
      </div>
    )}"""

    html = html.replace(
        "\n    </div>\n  );\n}\n\nReactDOM",
        modal_jsx + "\n    </div>\n  );\n}\n\nReactDOM",
    )

    html = html.replace(old_start, new_start)
    html = html.replace(old_send, new_send)
    return html


html_content = load_ui()
components.html(html_content, height=900, scrolling=False)
