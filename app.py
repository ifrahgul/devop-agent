import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from modules.analyzer import analyze_errors, ai_suggest_error
from io import BytesIO
from fpdf import FPDF

st.set_page_config(page_title="🚀 DevOps Log Analyzer Pro", layout="wide")
st.title("📊 DevOps Log Analyzer Pro")


def safe_datetime_conversion(series):
    converted = pd.to_datetime(
        series,
        errors="coerce",   
        utc=True
    )

    min_date = pd.Timestamp("2000-01-01", tz="UTC")
    max_date = pd.Timestamp("2100-01-01", tz="UTC")

    converted = converted.where(
        (converted >= min_date) & (converted <= max_date)
    )

    return converted


# --- Sidebar Controls ---
st.sidebar.title("⚙️ Settings")
use_ai = st.sidebar.toggle("🤖 Enable AI Assistance", value=True)
max_ai_calls = st.sidebar.slider("Max AI Calls", 1, 20, 5)

st.sidebar.markdown("### 📥 Log Input")
uploaded_files = st.sidebar.file_uploader(
    "Upload log files (.txt/.log)", 
    type=["txt", "log"], 
    accept_multiple_files=True
)

log_lines = []

if uploaded_files:
    for f in uploaded_files:
        try:
            content = f.read().decode("utf-8", errors="ignore")
            log_lines += [line for line in content.splitlines() if line.strip()]
        except Exception:
            st.sidebar.warning(f"Could not read file: {f.name}")
else:
    log_text = st.sidebar.text_area(
        "Or paste log lines (one per line)", 
        height=250
    )
    log_lines = [line for line in log_text.splitlines() if line.strip()]


# --- Filters ---
st.sidebar.markdown("### 🔎 Filters")
filter_confidence = st.sidebar.multiselect(
    "Filter by Confidence",
    options=["High", "Medium", "Low"],
    default=["High", "Medium", "Low"]
)

keyword_search = st.sidebar.text_input("Search logs (regex supported)")


# ---------------------------
# PROCESS LOGS
# ---------------------------

if log_lines:

    st.sidebar.write(f"Total log lines: {len(log_lines)}")

    summary, detailed = analyze_errors(log_lines, use_ai=use_ai)

  
    if use_ai:
        for log in detailed:
            try:
                log['ai_suggestion'] = ai_suggest_error(
                    log_line=log.get('log_line', ''),
                    probable_cause=log.get('probable_cause', ''),
                    confidence=log.get('confidence', ''),
                    timestamp=log.get('timestamp', '')
                )
            except Exception:
                log['ai_suggestion'] = "AI suggestion failed safely."

    df = pd.DataFrame(detailed)

    if 'ai_suggestion' not in df.columns:
        df['ai_suggestion'] = ""

    if df.empty:
        st.warning("⚠️ No errors detected in logs.")
    else:

        # Apply Filters
        df = df[df['confidence'].isin(filter_confidence)]

        if keyword_search:
            df = df[
                df['log_line'].str.contains(
                    keyword_search,
                    regex=True,
                    case=False,
                    na=False
                )
            ]

        # ---------------------------
        # SUMMARY METRICS
        # ---------------------------

        st.markdown("### 📌 Summary Metrics")
        col1, col2, col3 = st.columns(3)

        col1.metric("Total Errors", len(df))
        col2.metric(
            "Unknown Errors", 
            len(df[df['probable_cause']=="Unknown system error"])
        )
        col3.metric(
            "AI-Assisted Logs", 
            len(df[df['confidence']=="Low"])
        )

       

        st.markdown("### 🧩 Grouped Error Patterns")

        grouped = (
            df.groupby("probable_cause")
            .size()
            .reset_index(name="Occurrences")
            .sort_values(by="Occurrences", ascending=False)
        )

        if not grouped.empty:

            for _, row in grouped.iterrows():
                cause = row['probable_cause']
                count = row['Occurrences']

                with st.expander(f"{cause} ({count} occurrences)"):

                    subset = df[df['probable_cause']==cause].copy()

                    def color_conf(val):
                        if val=="High":
                            return "background-color: #d4edda"
                        elif val=="Medium":
                            return "background-color: #fff3cd"
                        else:
                            return "background-color: #f8d7da"

                    st.dataframe(
                        subset[
                            ['log_line','confidence',
                             'probable_cause','ai_suggestion',
                             'timestamp']
                        ].style.applymap(
                            color_conf,
                            subset=['confidence']
                        ),
                        use_container_width=True
                    )
        else:
            st.info("No grouped errors found.")

        if not grouped.empty:

            st.markdown("### 📊 Error Distribution")

            # Bar Chart
            fig, ax = plt.subplots()
            grouped.plot(
                kind="bar",
                x="probable_cause",
                y="Occurrences",
                ax=ax
            )
            ax.set_ylabel("Occurrences")
            ax.set_xlabel("Error Type")
            ax.set_title("Error Distribution")
            st.pyplot(fig)

            # Pie Chart
            fig2, ax2 = plt.subplots()
            ax2.pie(
                grouped['Occurrences'],
                labels=grouped['probable_cause'],
                autopct='%1.1f%%',
                startangle=140
            )
            ax2.set_title("Error Distribution")
            st.pyplot(fig2)


        st.markdown("### ⏱ Error Timeline")

        timeline_df = df.dropna(subset=['timestamp']).copy()

        if not timeline_df.empty:

            timeline_df['timestamp'] = safe_datetime_conversion(
                timeline_df['timestamp']
            )

            timeline_df = timeline_df.dropna(subset=['timestamp'])

            if not timeline_df.empty:

                timeline_grouped = (
                    timeline_df
                    .groupby(timeline_df['timestamp'].dt.date)
                    .size()
                    .reset_index(name="Errors")
                )

                timeline_grouped.columns = ['Date', 'Errors']

                st.line_chart(
                    timeline_grouped.set_index('Date')
                )
            else:
                st.warning("⚠ All timestamps invalid or out-of-range.")

        else:
            st.info("No timestamps detected.")

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "📥 Download CSV",
            csv,
            "log_analysis.csv",
            "text/csv"
        )

        if st.button("📄 Generate PDF Report"):

            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "DevOps Log Analyzer Pro Report",
                     ln=True, align='C')
            pdf.ln(10)

            pdf.set_font("Arial", size=12)
            pdf.cell(0, 10, f"Total Errors: {len(df)}", ln=True)
            pdf.ln(5)

            for _, row in grouped.iterrows():
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(
                    0, 8,
                    f"{row['probable_cause']} "
                    f"({row['Occurrences']} occurrences)",
                    ln=True
                )

                subset = df[df['probable_cause']==row['probable_cause']]

                pdf.set_font("Arial", size=10)

                for i, log in enumerate(subset['log_line'].tolist()):
                    suggestion = subset['ai_suggestion'].tolist()[i]
                    pdf.multi_cell(
                        0, 6,
                        f"{i+1}. {log}\nAI Suggestion: {suggestion}"
                    )

                pdf.ln(5)

            pdf_bytes = pdf.output(dest='S').encode('latin1')

            st.download_button(
                "📥 Download PDF",
                pdf_bytes,
                "log_analysis_report.pdf",
                "application/pdf"
            )

else:
    st.info("⏳ Paste logs or upload log files in sidebar.")
