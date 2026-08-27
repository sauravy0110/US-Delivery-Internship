"""
Thin Streamlit UI so a non-technical TAM/support agent can actually use
Task 1 (triage) and Task 2 (account brief) without touching the API directly.

Run: streamlit run ui/streamlit_app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app import data_loader
from app.account_brief import generate_account_brief
from app.triage import triage_ticket
from app.schemas import TicketInput

st.set_page_config(page_title="Support & TAM AI Tools", layout="wide")
st.title("Internal AI Tools — Support Triage & Account Briefs")

tab1, tab2 = st.tabs(["🎫 Ticket Triage", "📋 Account Brief"])

with tab1:
    st.subheader("Classify an incoming support ticket")
    subject = st.text_input("Ticket subject", placeholder="e.g. DataBridge Pro Connectors failing")
    body = st.text_area("Ticket body", height=180, placeholder="Paste the full ticket text here…")

    if st.button("Triage ticket", type="primary"):
        if not subject.strip() or not body.strip():
            st.warning("Please fill in both subject and body.")
        else:
            with st.spinner("Classifying…"):
                result = triage_ticket(TicketInput(subject=subject, body=body))
            c1, c2, c3 = st.columns(3)
            c1.metric("Urgency", result.urgency_tier)
            c2.metric("Category", result.issue_category)
            c3.metric("Responder team", result.recommended_responder_team)

            st.markdown("**Reasoning**")
            st.write(result.reasoning)

            st.markdown("**Draft first response**")
            st.text_area("Draft (editable — copy into your reply)", value=result.draft_first_response, height=140)

            if result.kb_matches:
                st.markdown("**Matched knowledge-base articles**")
                for m in result.kb_matches:
                    with st.expander(f"{m.doc_path} — {m.heading} (score {m.score})"):
                        st.write(m.excerpt)
            else:
                st.caption("No closely matching KB article found.")

with tab2:
    st.subheader("Generate a TAM account brief")
    try:
        accounts = data_loader.load_accounts()
        options = {f"{a['company']} ({a['account_id']})": a["account_id"] for a in accounts}
        choice = st.selectbox("Account", list(options.keys())) if options else None
    except FileNotFoundError:
        st.error("data/accounts.json not found. Run scripts/generate_sample_data.py or add the real dataset.")
        choice = None

    manual_id = st.text_input("...or enter an account_id directly", placeholder="ACC-1234")

    if st.button("Generate brief", type="primary"):
        account_id = manual_id.strip() or (options.get(choice) if choice else None)
        if not account_id:
            st.warning("Select or enter an account_id.")
        else:
            with st.spinner("Generating brief…"):
                brief = generate_account_brief(account_id)
            if not brief.found:
                st.error(brief.error)
            else:
                st.markdown(f"### {brief.company} ({brief.account_id})")
                st.markdown("**Executive summary**")
                st.write(brief.executive_summary)

                st.markdown(f"**Open risks & flagged issues** ({len(brief.open_risks_and_flags)})")
                if brief.open_risks_and_flags:
                    for f in brief.open_risks_and_flags:
                        st.markdown(f"- **{f.signal}** — _\"{f.justification_quote}\"_"
                                     + (f" (`{f.ticket_id}`)" if f.ticket_id else ""))
                else:
                    st.caption("No risk signals detected.")

                st.markdown("**Recommended talking points**")
                for p in brief.recommended_talking_points:
                    st.markdown(f"- {p}")

                st.caption(f"Based on {brief.tickets_considered} ticket(s) from the last 90 days · "
                            f"prompt version: {brief.prompt_version}")
