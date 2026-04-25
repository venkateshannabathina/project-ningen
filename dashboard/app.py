#!/usr/bin/env python3
"""
Ningen — AI Board Meeting System
Gradio frontend for board_meeting.py
Run: venv/bin/python dashboard/app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import gradio as gr
from pathlib import Path

from board_meeting import (
    initialize_context,
    api_run_opening_round,
    api_generate_questions,
    api_apply_clarifications,
    api_run_reaction_round,
    api_detect_conflicts_return,
    api_run_resolution_round,
    api_generate_requirements,
    save_output,
    save_briefings,
    AGENTS,
)

# ── Agent colours ──────────────────────────────────────────────────────────────
COLORS = {
    "CEO": "#F5A04A", "CTO": "#378ADD",
}

# ── Agent details formatter ────────────────────────────────────────────────────
def get_agent_info_html(speaker: str) -> str:
    if not speaker or speaker not in AGENTS:
        return '<div style="display:none;"></div>'
    
    info = AGENTS[speaker]
    role = info.get("role", "")
    personality = info.get("personality", "").replace(" Keep responses to 3-5 focused sentences.", "")
    col = COLORS.get(speaker, "#FFFFFF")
    
    return f"""
    <div style="border: 2px solid {col}40; border-left: 4px solid {col}; background: #0D0D1D; border-radius: 12px; padding: 16px; margin-bottom: 16px; margin-top: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.6);">
        <div style="display: flex; align-items: center; margin-bottom: 14px;">
            <div style="width: 50px; height: 50px; border-radius: 50%; background: {col}; box-shadow: 0 0 15px {col}80; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px; color: #0A0A1A; margin-right: 16px; flex-shrink: 0;">
                {speaker[:2]}
            </div>
            <div>
                <div style="font-size: 16px; font-weight: 900; color: {col}; letter-spacing: 1px;">{speaker} IS SPEAKING</div>
                <div style="font-size: 11px; color: #8888AA; text-transform: uppercase; letter-spacing: 2px; font-weight: 600;">{role}</div>
            </div>
        </div>
        <div style="font-size: 13px; color: #D0D0E0; line-height: 1.6; border-top: 1px solid #1A1A3A; padding-top: 12px; font-style: italic;">
            <strong style="color: #FFFFFF; font-style: normal; font-weight: 700; letter-spacing: 1px; font-size: 11px; text-transform: uppercase;">Agent Profile:</strong><br>
            {personality}
        </div>
    </div>
    """

# ── Serialise / deserialise context via JSON string (avoids gr.State dict bug) ─
def ctx_to_str(ctx: dict) -> str:
    return json.dumps(ctx)

def str_to_ctx(s: str) -> dict:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}

def qs_to_str(q: dict) -> str:
    return json.dumps(q)

def str_to_qs(s: str) -> dict:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}

# ── Chatbot message formatters ─────────────────────────────────────────────────
def fmt_msg(d: dict) -> tuple:
    spk  = d.get("speaker", "")
    role = d.get("role", "")
    txt  = d.get("message", "").replace("\n", "<br>")
    typ  = d.get("type", "")
    col  = COLORS.get(spk, "#7A7AAA")

    if typ == "conflict":
        html = (
            f'<div style="border-left:4px solid #E8593C;padding:10px 14px;margin:4px 0;'
            f'background:#1E0807;border-radius:0 8px 8px 0;">'
            f'<div style="color:#E8593C;font-weight:700;font-size:13px;margin-bottom:6px;">'
            f'⚠ CONFLICT DETECTED</div>'
            f'<div style="color:#D0D0E0;line-height:1.7;font-size:13px;">{txt}</div></div>'
        )
    elif typ == "agreement":
        html = (
            f'<div style="border-left:4px solid #639922;padding:10px 14px;margin:4px 0;'
            f'background:#071A07;border-radius:0 8px 8px 0;">'
            f'<div style="color:#639922;font-weight:700;font-size:13px;margin-bottom:6px;">'
            f'✓ AGREEMENT REACHED</div>'
            f'<div style="color:#D0D0E0;line-height:1.7;font-size:13px;">{txt[:500]}</div></div>'
        )
    elif typ == "resolution_header":
        html = (
            f'<div style="text-align:center;color:#7A7AAA;border-top:1px solid #2A2A4A;'
            f'border-bottom:1px solid #2A2A4A;padding:10px;margin:8px 0;font-size:12px;'
            f'letter-spacing:2px;font-family:monospace;">⚖ {txt}</div>'
        )
    elif typ == "question":
        html = (
            f'<div style="border-left:4px solid {col};padding:10px 14px;margin:4px 0;'
            f'background:#0F1020;border-radius:0 8px 8px 0;">'
            f'<div style="color:{col};font-weight:700;font-size:13px;margin-bottom:6px;">'
            f'{spk} — {role} [QUESTION]</div>'
            f'<div style="color:#C8C8E8;line-height:1.7;font-size:13px;font-style:italic;">'
            f'❓ {txt}</div></div>'
        )
    else:
        label = f"{spk} — {role}"
        if typ:
            label += f" [{typ.upper()}]"
        html = (
            f'<div style="border-left:4px solid {col};padding:10px 14px;margin:4px 0;'
            f'background:#0F1020;border-radius:0 8px 8px 0;">'
            f'<div style="color:{col};font-weight:700;font-size:13px;margin-bottom:6px;">'
            f'{label}</div>'
            f'<div style="color:#D0D0E0;line-height:1.7;font-size:14px;">{txt}</div></div>'
        )
    return (None, html)  # tuple: (user_msg, bot_msg)


def fmt_sep(title: str) -> tuple:
    html = (
        f'<div style="text-align:center;color:#4A4A7A;border-top:1px solid #1A1A3A;'
        f'border-bottom:1px solid #1A1A3A;padding:10px;margin:10px 0;font-size:11px;'
        f'letter-spacing:3px;font-family:monospace;text-transform:uppercase;">'
        f'━━━ {title} ━━━</div>'
    )
    return (None, html)


def fmt_user(txt: str) -> tuple:
    html = (
        f'<div style="padding:10px 14px;background:#131330;border:1px solid #2A2A5A;'
        f'border-radius:8px;color:#C0C0E0;font-size:14px;line-height:1.6;">{txt}</div>'
    )
    return (html, None)  # tuple: (user_msg, bot_msg)


def cstate(speaking=None, conflicts=None, agreements=None) -> str:
    return json.dumps({
        "speaking":   speaking,
        "conflicts":  conflicts or [],
        "agreements": agreements or [],
    })


# ══════════════════════════════════════════════════════════════════════════════
# Boardroom canvas HTML + JavaScript
# ══════════════════════════════════════════════════════════════════════════════
BOARDROOM_HTML = """
<style>
  #brd-wrap {
    background: #0D0D1D; border-radius:16px;
    border:1px solid #1E1E3A; position:relative;
    overflow:hidden; width:100%; aspect-ratio:5/4;
  }
  #brd-canvas { width:100%; height:100%; display:block; }
  #brd-label {
    position:absolute; bottom:10px; left:0; right:0;
    text-align:center; font-size:11px; letter-spacing:2px;
    font-family:monospace; pointer-events:none;
    color:#555577; transition:color 0.4s;
  }
</style>
<div id="brd-wrap">
  <canvas id="brd-canvas" width="500" height="400"></canvas>
  <div id="brd-label">BOARD ROOM</div>
</div>
<script>
(function(){
  var AG={
    CEO:{x:250,y:72, color:"#F5A04A",ini:"CE",name:"CEO",short:"Chief Executive"},
    CTO:{x:408,y:195,color:"#378ADD",ini:"CT",name:"CTO",short:"Chief Technology"},
    CMO:{x:250,y:318,color:"#E8593C",ini:"CM",name:"CMO",short:"Chief Marketing"},
    COO:{x:92, y:195,color:"#639922",ini:"CO",name:"COO",short:"Chief Operating"},
  };
  var tick=0, st={speaking:null,conflicts:[],agreements:[]};

  function readSt(){
    try{
      var el=document.getElementById("cs-box");
      if(el){var ta=el.querySelector("textarea");if(ta&&ta.value)return JSON.parse(ta.value);}
    }catch(e){}
    return st;
  }

  function draw(s){
    var c=document.getElementById("brd-canvas");if(!c)return;
    var ctx=c.getContext("2d"),W=c.width,H=c.height;
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle="#0D0D1D";ctx.fillRect(0,0,W,H);
    // centre glow
    var g=ctx.createRadialGradient(W/2,H/2,10,W/2,H/2,160);
    g.addColorStop(0,"rgba(25,15,50,0.7)");g.addColorStop(1,"rgba(13,13,29,0)");
    ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
    // table shadow
    ctx.save();ctx.shadowColor="rgba(0,0,0,0.9)";ctx.shadowBlur=30;
    ctx.beginPath();ctx.ellipse(W/2,H/2,140,92,0,0,Math.PI*2);
    ctx.fillStyle="#150F0A";ctx.fill();ctx.restore();
    // table body
    ctx.save();ctx.beginPath();ctx.ellipse(W/2,H/2,138,90,0,0,Math.PI*2);
    ctx.fillStyle="#1A1614";ctx.fill();ctx.restore();
    // grain rings
    for(var r=0;r<5;r++){
      ctx.save();ctx.beginPath();ctx.ellipse(W/2,H/2,138-r*22,90-r*14,0,0,Math.PI*2);
      ctx.strokeStyle="rgba(255,200,100,0.03)";ctx.lineWidth=1;ctx.stroke();ctx.restore();
    }
    // table border
    ctx.save();ctx.beginPath();ctx.ellipse(W/2,H/2,138,90,0,0,Math.PI*2);
    ctx.strokeStyle="#F5A04A";ctx.lineWidth=1.5;ctx.globalAlpha=0.55;ctx.stroke();ctx.restore();
    // table label
    ctx.save();ctx.textAlign="center";ctx.textBaseline="middle";
    ctx.fillStyle="rgba(245,160,74,0.2)";ctx.font="10px monospace";
    ctx.fillText("BOARD MEETING",W/2,H/2);ctx.restore();
    // conflict lines
    var pulse=0.5+0.5*Math.sin(tick*0.05);
    if(s.conflicts){s.conflicts.forEach(function(pair){
      var a=AG[pair[0]],b=AG[pair[1]];if(!a||!b)return;
      ctx.save();ctx.setLineDash([8,4]);ctx.strokeStyle="#E8593C";ctx.lineWidth=2;
      ctx.globalAlpha=0.4+0.35*pulse;
      ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.restore();
    });}
    // agents
    Object.keys(AG).forEach(function(k){
      var ag=AG[k];
      var spk=s.speaking===k;
      var agr=s.agreements&&s.agreements.some(function(a){return typeof a==="string"&&a.indexOf(k)!==-1;});
      if(spk){
        for(var ri=0;ri<3;ri++){
          ctx.save();ctx.beginPath();ctx.arc(ag.x,ag.y,28+(ri+1)*10+pulse*7,0,Math.PI*2);
          ctx.strokeStyle=ag.color;ctx.lineWidth=1.5-ri*0.4;ctx.globalAlpha=(0.45-ri*0.13)*pulse;
          ctx.stroke();ctx.restore();
        }
        ctx.save();ctx.shadowColor=ag.color;ctx.shadowBlur=25+pulse*12;
        ctx.beginPath();ctx.arc(ag.x,ag.y,25,0,Math.PI*2);ctx.fillStyle=ag.color;ctx.fill();ctx.restore();
      }
      ctx.save();ctx.beginPath();ctx.arc(ag.x,ag.y,25,0,Math.PI*2);
      ctx.fillStyle=ag.color;ctx.globalAlpha=spk?1:0.85;ctx.fill();ctx.restore();
      ctx.save();ctx.beginPath();ctx.arc(ag.x,ag.y,25,0,Math.PI*2);
      ctx.strokeStyle="rgba(255,255,255,0.18)";ctx.lineWidth=1;ctx.stroke();ctx.restore();
      ctx.save();ctx.textAlign="center";ctx.textBaseline="middle";
      ctx.fillStyle="#0A0A1A";ctx.font="bold 13px monospace";
      ctx.fillText(ag.ini,ag.x,ag.y);ctx.restore();
      ctx.save();ctx.textAlign="center";ctx.textBaseline="top";
      ctx.fillStyle=spk?ag.color:"#CCCCCC";ctx.font=(spk?"bold ":"")+"12px sans-serif";
      ctx.fillText(ag.name,ag.x,ag.y+32);ctx.restore();
      ctx.save();ctx.textAlign="center";ctx.textBaseline="top";
      ctx.fillStyle="#555577";ctx.font="10px sans-serif";
      ctx.fillText(ag.short,ag.x,ag.y+47);ctx.restore();
      if(agr){
        ctx.save();ctx.fillStyle="#639922";ctx.font="bold 14px sans-serif";
        ctx.textAlign="center";ctx.textBaseline="middle";
        ctx.fillText("✓",ag.x+29,ag.y-22);ctx.restore();
      }
    });
  }

  function loop(){
    tick++;
    st=readSt();draw(st);
    var lbl=document.getElementById("brd-label");
    if(lbl){
      if(st.speaking&&AG[st.speaking]){lbl.style.color=AG[st.speaking].color;lbl.textContent=AG[st.speaking].name+" is speaking…";}
      else{lbl.style.color="#555577";lbl.textContent="BOARD ROOM";}
    }
    requestAnimationFrame(loop);
  }
  setTimeout(function(){draw(st);loop();},600);
})();
</script>
"""

CSS = """
*,*::before,*::after{box-sizing:border-box;}
body,.gradio-container,.main,#root{background:#0A0A1A!important;color:#E0E0F0!important;font-family:'Inter',system-ui,sans-serif!important;}
.gradio-container{max-width:100%!important;}
footer{display:none!important;}
::-webkit-scrollbar{width:6px;height:6px;}
::-webkit-scrollbar-track{background:#0A0A1A;}
::-webkit-scrollbar-thumb{background:#2A2A4A;border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:#F5A04A;}
.gr-box,.gr-form,.gr-panel,.gr-block{background:transparent!important;}
.dark-input textarea,.dark-input input[type=text]{background:#0F0F22!important;color:#E0E0F0!important;border:1px solid #2A2A4A!important;border-radius:8px!important;font-size:14px!important;line-height:1.6!important;}
.dark-input textarea:focus,.dark-input input[type=text]:focus{border-color:#F5A04A!important;box-shadow:0 0 0 3px rgba(245,160,74,.12)!important;outline:none!important;}
.dark-input label span{color:#555577!important;font-size:11px!important;letter-spacing:1px!important;text-transform:uppercase;}
.amber-btn{background:linear-gradient(135deg,#F5A04A,#E8853A)!important;color:#0A0A1A!important;font-weight:700!important;border:none!important;border-radius:8px!important;font-size:14px!important;letter-spacing:1px!important;transition:all .2s ease!important;cursor:pointer!important;box-shadow:0 2px 12px rgba(245,160,74,.2)!important;}
.amber-btn:hover{background:linear-gradient(135deg,#FFB86A,#F5A04A)!important;transform:translateY(-2px)!important;box-shadow:0 6px 24px rgba(245,160,74,.35)!important;}
.dark-chat{background:#070714!important;border:1px solid #1A1A3A!important;border-radius:12px!important;}
.dark-chat>div{background:#070714!important;}
.dark-chat .bubble-wrap,.dark-chat .message-wrap{background:transparent!important;}
.dark-chat .message.user,.dark-chat .message.bot{background:transparent!important;}
.q-panel{background:#0D0D22!important;border:1px solid #2A2A5A!important;border-radius:12px!important;padding:16px!important;}
.json-out{background:#0D0D1D!important;border:1px solid #1A1A3A!important;border-radius:12px!important;}
.json-out pre{background:transparent!important;color:#A0D0A0!important;}
#ningen-logo{font-family:monospace;font-size:26px;font-weight:900;color:#F5A04A;letter-spacing:4px;line-height:1;}
#ningen-sub{font-size:11px;color:#444466;letter-spacing:3px;text-transform:uppercase;margin-top:4px;}
"""

# ══════════════════════════════════════════════════════════════════════════════
# Phase generators  (all State is passed as JSON strings)
# ══════════════════════════════════════════════════════════════════════════════

def phase1(idea, chat):
    """Phase 1 — opening round + questions."""
    if not idea or not idea.strip():
        yield chat, "", cstate(), gr.update(visible=False), gr.update(visible=False), "", cstate(), get_agent_info_html(None)
        return

    ctx = initialize_context(idea.strip())
    chat = [fmt_user(f"💡 {idea.strip()}"), fmt_sep("ROUND 1 — OPENING POSITIONS")]
    cs = cstate()
    yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), "", cs, get_agent_info_html(None)

    for md in api_run_opening_round(ctx):
        chat = chat + [fmt_msg(md)]
        cs = cstate(speaking=md["speaker"])
        yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), "", cs, get_agent_info_html(md["speaker"])

    # Questions round
    chat = chat + [fmt_sep("CLIENT QUESTIONS ROUND")]
    cs = cstate()
    yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), "", cs, get_agent_info_html(None)

    ctx, q_msgs, questions = api_generate_questions(ctx)
    for md in q_msgs:
        chat = chat + [fmt_msg(md)]
        cs = cstate(speaking=md["speaker"])
        yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), qs_to_str(questions), cs, get_agent_info_html(md["speaker"])

    # Reveal questions input panel
    yield chat, ctx_to_str(ctx), cstate(), gr.update(visible=True), gr.update(visible=True), qs_to_str(questions), cstate(), get_agent_info_html(None)


def phase2(answer, chat, ctx_str, qs_str):
    """Phase 2 — reactions, conflicts, resolution, briefings, requirements."""
    ctx = str_to_ctx(ctx_str)
    questions = str_to_qs(qs_str)

    if not answer or not answer.strip():
        yield chat, ctx_str, cstate(), gr.update(visible=True), gr.update(visible=True), None, gr.update(visible=False), cstate(), get_agent_info_html(None)
        return

    ctx = api_apply_clarifications(ctx, answer.strip(), questions)
    chat = chat + [fmt_user(f"📝 {answer.strip()}"), fmt_sep("ROUND 2 — REACTIONS")]
    cs = cstate()
    yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), None, gr.update(visible=False), cs, get_agent_info_html(None)

    for md in api_run_reaction_round(ctx):
        chat = chat + [fmt_msg(md)]
        cs = cstate(speaking=md["speaker"])
        yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), None, gr.update(visible=False), cs, get_agent_info_html(md["speaker"])

    # Conflict detection
    chat = chat + [fmt_sep("CONFLICT DETECTION")]
    ctx, conflict_msgs = api_detect_conflicts_return(ctx)
    conflict_pairs = [c["conflict_data"]["agents_involved"] for c in conflict_msgs if "conflict_data" in c]
    cs = cstate(conflicts=conflict_pairs)
    for cm in conflict_msgs:
        chat = chat + [fmt_msg(cm)]
        yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), None, gr.update(visible=False), cs, get_agent_info_html(None)

    # Resolution
    chat = chat + [fmt_sep("ROUND 3 — CONFLICT RESOLUTION")]
    yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), None, gr.update(visible=False), cs, get_agent_info_html(None)

    for md in api_run_resolution_round(ctx):
        chat = chat + [fmt_msg(md)]
        agrs = ctx.get("agreed_on", [])
        cs = cstate(speaking=md.get("speaker"), conflicts=conflict_pairs, agreements=agrs)
        yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), None, gr.update(visible=False), cs, get_agent_info_html(md.get("speaker"))

    # Briefings
    briefing_store = {}
    chat = chat + [fmt_sep("FINAL AGENT BRIEFINGS")]
    cs = cstate(agreements=ctx.get("agreed_on", []))
    yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), None, gr.update(visible=False), cs, get_agent_info_html(None)

    for md in api_run_briefings(ctx):
        chat = chat + [fmt_msg(md)]
        briefing_store[md["speaker"]] = md["message"]
        cs = cstate(speaking=md["speaker"], agreements=ctx.get("agreed_on", []))
        yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), None, gr.update(visible=False), cs, get_agent_info_html(md["speaker"])

    save_briefings(briefing_store, ctx)

    # Requirements
    ctx, doc = api_generate_requirements(ctx)
    save_output(doc)

    out_path = str(Path("outputs/board_meeting_result.json").resolve())
    chat = chat + [fmt_sep("BOARD MEETING COMPLETE — AGENTS BRIEFED & READY TO EXECUTE")]
    cs = cstate(agreements=ctx.get("agreed_on", []))
    yield chat, ctx_to_str(ctx), cs, gr.update(visible=False), gr.update(visible=False), doc, gr.update(visible=True, value=out_path), cs, get_agent_info_html(None)


# ══════════════════════════════════════════════════════════════════════════════
# Gradio UI
# ══════════════════════════════════════════════════════════════════════════════
with gr.Blocks(css=CSS, title="Ningen — AI Board Meeting", theme=gr.themes.Base()) as demo:

    # State stored as JSON strings to avoid gr.State dict schema bug in Gradio 4.44+Py3.9
    ctx_state = gr.State(value="")
    qs_state  = gr.State(value="")

    gr.HTML('<style>body{background:#0A0A1A!important;}.gradio-container{background:#0A0A1A!important;}</style>')

    with gr.Row(equal_height=False):

        # ── Left column: animated boardroom canvas ─────────────────────────────
        with gr.Column(scale=6, min_width=340):
            gr.HTML(BOARDROOM_HTML)
            # Hidden textbox polled by canvas JS (elem_id must match canvas script)
            canvas_box = gr.Textbox(
                value=cstate(), visible=False,
                elem_id="cs-box", label="canvas_state",
            )

        # ── Right column: interaction panel ───────────────────────────────────
        with gr.Column(scale=4, min_width=320):

            gr.HTML(
                '<div style="padding:20px 0 12px 0;">'
                '<div id="ningen-logo">NINGEN</div>'
                '<div id="ningen-sub">AI Board Meeting System · gpt-4o-mini</div>'
                '</div>'
            )

            idea_input = gr.Textbox(
                placeholder="Describe your startup idea…",
                label="CLIENT IDEA",
                lines=3, max_lines=6,
                elem_classes=["dark-input"],
            )

            convene_btn = gr.Button("⚡ Convene Board", elem_classes=["amber-btn"], size="lg")

            agent_details_box = gr.HTML('<div style="display:none;"></div>')

            chatbot = gr.Chatbot(
                label="", height=440,
                show_label=False,
                render_markdown=True,
                sanitize_html=False,
                elem_classes=["dark-chat"],
                bubble_full_width=True,
            )

            # Client questions panel (hidden until after Round 1)
            with gr.Group(visible=False, elem_classes=["q-panel"]) as q_panel:
                gr.HTML(
                    '<div style="color:#F5A04A;font-size:12px;font-weight:700;'
                    'letter-spacing:2px;margin-bottom:8px;">YOUR TURN — ANSWER ALL FOUR QUESTIONS</div>'
                )
                answers_input = gr.Textbox(
                    placeholder="Answer all four agent questions above in one response…",
                    label="CLIENT CLARIFICATIONS",
                    lines=4, max_lines=10,
                    elem_classes=["dark-input"],
                )
                submit_btn = gr.Button(
                    "Submit Answers & Continue Meeting →",
                    elem_classes=["amber-btn"], size="sm",
                )

            requirements_json = gr.JSON(
                label="FINAL REQUIREMENTS DOCUMENT",
                visible=False,
                elem_classes=["json-out"],
            )

            download_file = gr.File(
                label="⬇ Download Requirements JSON",
                visible=False,
                interactive=False,
                elem_classes=["json-out"],
            )

    # ── Wiring ─────────────────────────────────────────────────────────────────
    # Outputs: chatbot, ctx_state, canvas_box, q_panel, submit_btn, qs_state, canvas_box(2nd=elem_id sync), agent_details_box
    p1_out = [chatbot, ctx_state, canvas_box, q_panel, submit_btn, qs_state, canvas_box, agent_details_box]

    convene_btn.click(fn=phase1, inputs=[idea_input, chatbot], outputs=p1_out, queue=True)
    idea_input.submit(fn=phase1, inputs=[idea_input, chatbot], outputs=p1_out, queue=True)

    # Outputs: chatbot, ctx_state, canvas_box, q_panel, submit_btn, requirements_json, download_file, canvas_box, agent_details_box
    p2_out = [chatbot, ctx_state, canvas_box, q_panel, submit_btn, requirements_json, download_file, canvas_box, agent_details_box]

    submit_btn.click(fn=phase2, inputs=[answers_input, chatbot, ctx_state, qs_state], outputs=p2_out, queue=True)


if __name__ == "__main__":
    import socket
    def _free(p):
        with socket.socket() as s:
            return s.connect_ex(("127.0.0.1", p)) != 0
    port = next((p for p in range(7860, 7880) if _free(p)), 7860)
    print(f"\n🚀  Ningen launching → http://localhost:{port}\n")
    demo.queue().launch(
        server_name="127.0.0.1",
        server_port=port,
        show_api=False,
        share=False,
        quiet=True,
    )
