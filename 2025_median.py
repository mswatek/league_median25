import streamlit as st
from espn_api.football import League
import pandas as pd
import numpy as np
import plotly.express as px

# Inject CSS for theme-aware styling
st.markdown("""
    <style>
    .highlight td {
        background-color: #d4f4dd !important;
        color: black !important;
    }
    </style>
""", unsafe_allow_html=True)

# App title
st.title("📊 2025 Median Calculator")

# ESPN credentials
LEAGUE_ID = 363545
ESPN_S2 = "AEB1H1ln2qqhTEkIb1l3Pg5I7s%2FYoTzF3YaWm7cByfVP58hiQRo%2FoCApJ7hxkwkkS2T%2BaA%2FE1CRaTLmjPqO5MiocFcYvXtsvF8Lp8lhNoMKI7mNrmE9u%2BsyrDvOnH9L%2BGm2Yk1LAe4XwtQFFrfWoaPnV3eXz%2BYb5M7Zi5tlAFmUbUujGTa3BrR%2BuQI3Ik1yvr%2Fq%2FFSRd90Nc6NtJLIPPVRXOg2%2BUUP1B4aor5WEIaejxHq%2F4nsVKZHT3dmYZLsG0dG3L0ChQJHeXFLeVKh8JrbtF"
SWID = "{3A92DF39-2D04-4F76-92B3-A92DFE5A5565}"

# Initialize league once
league = League(league_id=LEAGUE_ID, year=2025, espn_s2=ESPN_S2, swid=SWID)

# Week selector
current_week = league.current_week
selected_week = st.selectbox("Select Week", options=list(range(1, current_week + 1)), index=current_week - 1)

st.subheader(f"🏈 Week {selected_week} Projected Median")

# Collect team scores for selected week
team_data = []

scoreboard = league.scoreboard(week=selected_week)

for matchup in scoreboard:
    for team, score in zip([matchup.home_team, matchup.away_team], [matchup.home_score, matchup.away_score]):

        # Past weeks: use final score
        if selected_week < current_week:
            team_data.append({
                "Team": team.team_name,
                "Score": round(score, 2),
                "Status": "Final",
                "Actual": score,
                "Remaining": 0
            })

        # Current week: calculate live + projected
        elif selected_week == current_week:
            actual = 0
            remaining = 0

            for player in team.roster:
                if getattr(player, "lineupSlot", "BE") in ["BE", "IR"]:
                    continue

                points = getattr(player, "points", 0) or 0
                projected = getattr(player, "projected_points", None)
                if projected is None:
                    projected = getattr(player, "projected_avg_points", 0)

                actual += points
                remaining += projected

            total_projection = actual + remaining
            status = "Final" if remaining == 0 else "Ongoing"

            team_data.append({
                "Team": team.team_name,
                "Score": round(total_projection, 2),
                "Status": status,
                "Actual": actual,
                "Remaining": remaining
            })

        # Future weeks: use projected totals only
        else:
            projected_total = sum(
                getattr(player, "projected_points", 0) or 0
                for player in team.roster
                if getattr(player, "lineupSlot", "BE") not in ["BE", "IR"]
            )

            team_data.append({
                "Team": team.team_name,
                "Score": round(projected_total, 2),
                "Status": "Projected",
                "Actual": 0,
                "Remaining": projected_total
            })

# Create DataFrame
df_scores = pd.DataFrame(team_data)

# Calculate median
median_score = round(np.median(df_scores["Score"]), 2)

# Run Monte Carlo simulations for % Median Win
simulated_probs = []
for row in df_scores.itertuples():
    if row.Status == "Final":
        prob = 100.0 if row.Score > median_score else 0.0
    else:
        std_dev = 0.15 * row.Remaining
        sims = np.random.normal(loc=row.Score, scale=std_dev, size=1000)
        prob = np.mean(sims > median_score) * 100
    simulated_probs.append(prob)

# Normalize to sum to 600%
total_prob = sum(simulated_probs)
normalized_probs = [round(p * 600 / total_prob, 1) for p in simulated_probs]
df_scores["% Median Win"] = normalized_probs

# Flag teams above median
df_scores["Highlight"] = df_scores["Score"] > median_score
df_scores = df_scores.sort_values("Score", ascending=False).reset_index(drop=True)

# Drop highlight column for display
df_display = df_scores.drop(columns=["Highlight", "Actual", "Remaining"])

# Style function with inline CSS
def highlight_rows(row):
    return ['background-color: #d4f4dd; color: black;' if row["Score"] > median_score else '' for _ in row]

# Apply styling
styled_df = df_display.style.apply(highlight_rows, axis=1).format({
    "Score": "{:.2f}",
    "% Median Win": "{:.1f}%"
})

# Display results
st.metric(label="Projected Median Score", value=f"{median_score:.2f}")
st.caption("Status reflects live scoring. % Median Win is a simulation-based forecast normalized to 600%.")
st.dataframe(styled_df, use_container_width=True)


if selected_week == current_week:
    st.subheader("📈 Simulated Median Distribution")

    # Simulate final scores for each team
    team_simulations = []
    for row in df_scores.itertuples():
        if row.Status == "Final":
            sims = np.full(1000, row.Score)
        else:
            std_dev = 0.15 * row.Remaining
            sims = np.random.normal(loc=row.Score, scale=std_dev, size=1000)
        team_simulations.append(sims)

    # Transpose to get 1000 simulations of league-wide scores
    team_simulations = np.array(team_simulations)
    simulated_medians = np.median(team_simulations, axis=0)

    # Plot histogram
    fig_median = px.histogram(
        x=simulated_medians,
        nbins=30,
        title="Distribution of Simulated Median Scores",
        labels={"x": "Simulated Median Score"},
    )
    fig_median.update_layout(
        xaxis_title="Median Score",
        yaxis_title="Frequency",
        bargap=0.1,
        showlegend=False
    )
    fig_median.add_vline(
        x=median_score,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Projected Median: {median_score:.2f}",
        annotation_position="top right"
    )
    st.plotly_chart(fig_median, use_container_width=True)
