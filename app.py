import base64
import html
from datetime import timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import invite
import mailer

st.set_page_config(page_title="Picnic?", page_icon="🧺")

ROOT = Path(__file__).parent
KITTY_PARTS = ("kitty_body", "kitty_arm_l", "kitty_arm_r")  # 21x24 pixel sprite, arms split out
WALLPAPER_PATH = ROOT / "assets" / "hello_wallpaper.png"
COUPLE_PATH = ROOT / "assets" / "kitty_couple.png"

NO_TEXTS = ["No"]  # first label; after that the button cycles through NO_CYCLE forever
NO_CYCLE = [
    "Are you sure?",
    "Pretty please?",
    "I'll bring snacks...",
    "I know you want to!",
    "Think of the strawberries!",
    "Don't break my heart...",
    "Just say yes!",
]

# --- state: survives reruns ---
st.session_state.setdefault("no_clicks", 0)
st.session_state.setdefault("answered_yes", False)
st.session_state.setdefault("celebrated", False)
st.session_state.setdefault("planning", False)  # the "customize our picnic" form is open
st.session_state.setdefault("sent", None)  # result of the invite attempt
st.session_state.setdefault("her_email", "")


def data_uri(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def on_yes():
    st.session_state.answered_yes = True


def on_no():
    st.session_state.no_clicks += 1


def toggle_planner():
    st.session_state.planning = not st.session_state.planning


# --- inject css + js ---
css = (ROOT / "assets" / "style.css").read_text()
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

confetti_lib = (ROOT / "assets" / "confetti.browser.min.js").read_text()
js = (ROOT / "assets" / "effects.js").read_text()
components.html(f"<script>{confetti_lib}</script><script>{js}</script>", height=0)

def send(plan, her_email):
    """Email her the confirmation (+ me a copy of her picks) and, if the calendar is set up, send the Meet invite.
    Never raises; every part reports its own status."""
    start, end = invite.next_saturday()
    result = {"plan": plan, "start": start, "her_email": her_email}
    mailer.log_submission(plan, her_email)  # local backup of what she picked

    mail_cfg = mailer.settings_from(st.secrets)
    if mail_cfg is None:
        result["mail"] = "not_configured"
    else:
        try:
            mailer.send_all(mail_cfg, mailer.build_messages(mail_cfg, plan, her_email, start, end))
            result["mail"] = "sent"
        except Exception as e:
            result.update(mail="error", error=str(e))

    cal_cfg = invite.settings_from(st.secrets)
    if cal_cfg is None:
        result["status"] = "not_configured"
    else:
        try:
            result.update(status="sent", **invite.send_invite(plan, cal_cfg, her_email))
        except Exception as e:
            result.update(status="error", error=str(e))
    return result


def show_result(sent):
    plan, start = sent["plan"], sent["start"]
    when = start.strftime("%A, %B %-d at %-I:%M %p")
    if sent["mail"] == "sent":
        title, note = "It's a date!", f"A confirmation is on its way to {html.escape(sent['her_email'])}, and I've got your picks too."
    elif sent["mail"] == "error":
        title, note = "Oops", "The confirmation email didn't go through, but you can still add it to your calendar below."
    else:
        title, note = "Picks saved!", "Add the picnic to your calendar below."
    if sent["status"] == "sent":
        note += f" A Google Meet invite for {when} is coming too."

    rows = [
        f"<tr><th>{label}</th><td>{html.escape(plan[key])}</td></tr>"
        for label, key in (("Where", "where"), ("Food", "food"), ("Drinks", "drinks"), ("Skip", "avoid"))
        if plan.get(key)
    ]
    table = f'<table class="details requests">{"".join(rows)}</table>' if rows else ""
    fine_print = (
        '<p class="fine-print">Email isn\'t connected yet (see secrets.toml.example).</p>'
        if sent["mail"] == "not_configured"
        else ""
    )
    st.markdown(
        f'<div class="sent-card"><div class="form-title">{title}</div><p>{note}</p>{fine_print}</div>{table}',
        unsafe_allow_html=True,
    )

    # works on an iPhone with no setup: the .ics opens straight in Calendar
    ics = invite.make_ics(plan, start, start + timedelta(minutes=invite.EVENT_MINUTES), sent.get("meet"))
    st.download_button("Add to calendar", ics, "picnic-date.ics", "text/calendar", key="ics_btn", on_click="ignore")
    if "error" in (sent["mail"], sent["status"]):
        if st.button("Try again", key="retry_btn"):
            st.session_state.sent = None
            st.rerun()


# --- screens ---
if st.session_state.answered_yes:
    if WALLPAPER_PATH.exists():  # style.css reads this var on the yes screen
        st.markdown(
            f'<style>:root {{ --yes-wallpaper: url("{data_uri(WALLPAPER_PATH)}"); }}</style>',
            unsafe_allow_html=True,
        )

    st.title("Yay!")

    with st.container(key="jump_gif"):  # css targets .st-key-jump_gif
        body, arm_l, arm_r = (data_uri(ROOT / "assets" / f"{name}.png") for name in KITTY_PARTS)
        st.markdown(  # effects.js adds the floating hearts; style.css animates the arms
            f"""<div class="kitty"><div class="dancer">
            <img class="body" src="{body}"><img class="arm arm-l" src="{arm_l}"><img class="arm arm-r" src="{arm_r}">
            </div></div>""",
            unsafe_allow_html=True,
        )

    if not st.session_state.celebrated:  # fire confetti once, not on every rerun
        # effects.js exposes kittyConfetti() on the page; retry briefly in case it isn't mounted yet
        components.html(
            """<script>
            (function fire(tries) {
              const p = window.parent;
              if (p.kittyConfetti) p.kittyConfetti();
              else if (tries < 40) setTimeout(() => fire(tries + 1), 100);
            })(0);
            </script>""",
            height=0,
        )
        st.session_state.celebrated = True

    st.markdown(
        f"""
        <table class="details">
          <tr><th>Where</th><td>{invite.DEFAULT_PLACE}</td></tr>
          <tr><th>When</th><td>{invite.WHEN_TEXT}</td></tr>
          <tr><th>Bring</th><td>{invite.DEFAULT_BRING}</td></tr>
        </table>
        """,
        unsafe_allow_html=True,
    )

    sent = st.session_state.sent
    if sent:
        show_result(sent)
    else:
        with st.container(key="email_box"):  # css targets .st-key-email_box
            st.markdown('<div class="form-title">Where should I send your confirmation?</div>', unsafe_allow_html=True)
            her_email = st.text_input("Your email", key="her_email", placeholder="you@example.com")

        st.button("Close customizing" if st.session_state.planning else "Customize our picnic", key="plan_btn", on_click=toggle_planner)

        plan = {"where": "", "food": "", "drinks": "", "avoid": ""}
        if st.session_state.planning:
            with st.container(key="plan_fields"):  # css targets .st-key-plan_fields
                st.markdown('<div class="form-title">Let\'s plan it together</div>', unsafe_allow_html=True)
                plan["where"] = st.text_input("Somewhere else in mind?", key="plan_where", placeholder="Mission Dolores Park is the plan")
                plan["food"] = st.text_area("Food you're craving", key="plan_food", placeholder="cheese board, strawberries, sandwiches...", height=80)
                plan["drinks"] = st.text_area("Beverages", key="plan_drinks", placeholder="sparkling lemonade, a nice rose...", height=80)
                plan["avoid"] = st.text_area("Anything you don't like or can't eat?", key="plan_avoid", placeholder="allergies, picky bits, no olives...", height=80)

        # a separate button, so she can send without customizing anything
        if st.button("Send the invite", key="send_btn"):
            if mailer.valid_email(her_email):
                st.session_state.sent = send({k: v.strip() for k, v in plan.items()}, her_email.strip())
                st.rerun()
            else:
                st.markdown('<p class="field-error">Pop your email in above so I can send the confirmation.</p>', unsafe_allow_html=True)

else:
    st.title("Picnic at Dolores Park this Saturday?")

    if COUPLE_PATH.exists():
        with st.container(key="couple_img"):  # css targets .st-key-couple_img
            st.image(str(COUPLE_PATH), width=320)

    n = st.session_state.no_clicks
    yes_size = min(1.6 + 0.4 * n, 4)  # Yes grows with each real "No" click
    st.markdown(
        f"<style>.st-key-yes_btn button p {{ font-size: {yes_size}rem; }}</style>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.button("Yes", key="yes_btn", on_click=on_yes)
    with col2:
        st.button(NO_TEXTS[0] if n == 0 else NO_CYCLE[(n - 1) % len(NO_CYCLE)], key="no_btn", on_click=on_no)