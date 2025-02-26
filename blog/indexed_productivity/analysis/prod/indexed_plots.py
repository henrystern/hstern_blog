"""Recreate the OurWorldInData productivity plots and compare to plots from different index years and overall levels."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
import prod.plotly_theme as pt  # noqa: F401
from prod.config import OUTPUT_DIR, RAW_DATA_DIR

pio.templates.default = "hstern_dark"
# pio.templates.default = "hstern_light"

data_source_note = (
    "Data source: Feenstra et al. (2015), Penn World Table 10.1 (2021)"
)
lp_description = "Note: labour productivity is output GDP per hour worked by employee at 2017 USD, PPP adjusted."
key_countries = [
    "United States",
    "Germany",
    "France",
    "Australia",
    "Canada",
    "Italy",
    "United Kingdom",
    "Japan",
]
country_palette = {  # So plots all use the same colors for each country.
    country: hue
    for country, hue in zip(
        key_countries, pio.templates["hstern_dark"].layout.colorway
    )
}


def main(output=True):
    """Read and analyse the PWT"""
    pwt = read_pwt("pwt1001")
    lp = select_relevant_data(pwt)
    lp_indexed = pd.concat(
        [index_at_year(lp, at_year=year) for year in range(1950, 2020)]
    ).reset_index()

    fig = {}
    fig["lp_level_all_years"] = (
        formatted_line_plot(
            lp,
            dict(
                y="labor_productivity",
                title="Labour productivity level by year<br><sup>U.S. productivity has been unmatched for the last 75 years.",
            ),
            "<br>".join([data_source_note, lp_description]),
        )
        .update_yaxes(range=[0.01, 80])
        .update_layout(legend=inset_legend_layout())
    )
    # fig["lp_level_all_years"].show(
    #     config=pt.get_config_options("lp_level_all_years")
    # )

    fig["lp_growth_1990"] = (
        formatted_line_plot(
            lp_indexed[lambda x: x["index_year"] == 1990],
            dict(
                title="Labour productivity growth since 1990<br><sup>Germany is impressively far ahead"
            ),
            [data_source_note, lp_description],
        )
        .update_xaxes(range=[1989, 2020])
        .update_yaxes(title="Index (1990=100)", range=[100, 200])
        .update_layout(
            legend=inset_legend_layout(),
        )
    )
    # fig["lp_growth_1990"].show(config=pt.get_config_options("lp_growth_1990"))

    fig["lp_growth_2007"] = (
        formatted_line_plot(
            lp_indexed[lambda x: x["index_year"] == 2007],
            dict(
                title="Labour productivity growth since 2007<br><sup>The U.S. is doing better?"
            ),
        )
        .update_xaxes(range=[2006, 2020])
        .update_yaxes(title="Index (2007=100)", range=[95, 125])
        .update_layout(legend=inset_legend_layout())
    )
    # fig["lp_growth_2007"].show(config=pt.get_config_options("lp_growth_2007"))

    fig["lp_growth_all_years"] = formatted_line_plot(
        lp_indexed[
            lambda x: (x["year"] > x["index_year"] - 1)
            & (x["index_year"].between(1970, 2015))
        ],
        dict(
            title="Find your narrative's base year",
            animation_frame="index_year",
        ),
    )
    for frame in fig["lp_growth_all_years"].frames:
        frame_high = lp_indexed.loc[
            lambda x: x["index_year"] == int(frame.name),
            "indexed_labor_productivity",
        ].max()
        frame["layout"].update(yaxis_range=[90, frame_high + 5])
    fig["lp_growth_all_years"].layout.updatemenus[0].buttons[0].args[1][
        "transition"
    ]["duration"] = 0
    # fig["lp_growth_all_years"].show(
    #     config=pt.get_config_options("lp_growth_all_years")
    # )

    fig["lp_growth_around_1990"] = formatted_line_plot(
        lp_indexed[
            lambda x: (x["year"] > x["index_year"] - 1)
            & (x["year"] > 1989)
            & (x["index_year"].isin([1989, 1991]))
        ],
        dict(
            title="Labour Productivity Growth<br><sup>A few years can make a big difference",
            facet_col="index_year",
        ),
        [
            data_source_note,
            "Note: German reunification accounts for most of Germany's excess growth since 1990.",
        ],
    ).for_each_annotation(
        lambda a: a
        if "Base year" not in a.text
        else a.update(text=f"{a.text.split('=')[-1]}=100")
    )
    # fig["lp_growth_around_1990"].show(
    #     config=pt.get_config_options("lp_growth_around_1990")
    # )

    fig["lp_growth_around_1993"] = formatted_line_plot(
        lp_indexed[
            lambda x: (x["year"] > x["index_year"] - 1)
            & (x["year"] > 1992)
            & (x["index_year"].isin([1992, 1993, 1994]))
        ],
        dict(
            title="Labour Productivity Growth<br><sup>1992-1994 is more representative",
            facet_col="index_year",
        ),
        [
            data_source_note,
            "Note: there were fewer major shocks from 1992-1993.",
        ],
    ).for_each_annotation(
        lambda a: a
        if "Base year" not in a.text
        else a.update(text=f"{a.text.split('=')[-1]}=100")
    )
    # fig["lp_growth_around_1993"].show(
    #     config=pt.get_config_options("lp_growth_around_1993")
    # )

    lp_indexed_selected_countries = pd.concat(
        [
            lp_indexed.loc[
                lambda x: (x["year"] > 1984)
                & (x["index_year"] == 1985)
                & (x["country"].isin(["United States", "United Kingdom"]))
            ].assign(context="U.K. catching up to global leader"),
            lp_indexed.loc[
                lambda x: (x["year"] > 1984)
                & (x["index_year"] == 1985)
                & (
                    x["country"].isin(
                        [
                            "France",
                            "Germany",
                            "United Kingdom",
                        ]
                    )
                )
            ].assign(context="U.K. lagging peer countries"),
        ]
    )

    fig["lp_growth_1985_countries"] = (
        formatted_line_plot(
            lp_indexed_selected_countries,
            dict(
                title="Labour Productivity Growth Since 1985",
                facet_col="context",
            ),
            [data_source_note, "Note: both are true."],
            shown_countries=[
                "United States",
                "Germany",
                "United Kingdom",
                "France",
            ],
        )
        .for_each_annotation(
            lambda a: a
            if "context" not in a.text
            else a.update(
                text=a.text.split("=")[-1],
                font_size=16,
                font_color=pt.colour["light_pink"],
            )
        )
        .update_layout(
            yaxis_title="Index (1985=100)", legend=inset_legend_layout()
        )
    )
    # fig["lp_growth_1985_countries"].show(
    #     config=pt.get_config_options("lp_growth_1985_countries")
    # )

    fig["lp_growth_canada"] = formatted_line_plot(
        lp_indexed[
            lambda x: (x["year"] > x["index_year"] - 1)
            & (x["year"] > 2008)
            & (x["index_year"].isin([2008, 2009]))
        ],
        dict(
            title="Labour Productivity Growth<br><sup>Canada leading since 2009?",
            facet_col="index_year",
        ),
    ).for_each_annotation(
        lambda a: a
        if "index_year" not in a.text
        else a.update(text=f"{a.text.split('=')[-1]}=100")
    )
    # fig["lp_growth_canada"].show(
    #     config=pt.get_config_options("lp_growth_canada")
    # )

    if output:
        output_all_figs(fig, out_dir=Path(OUTPUT_DIR))
    return fig


def output_all_figs(fig, exclude=[], out_dir=OUTPUT_DIR):
    """Output all the figs in fig to a file based on their key"""
    for name, f in fig.items():
        if name in exclude:
            continue
        f.write_html(
            out_dir / f"{name}.html",
            config=pt.get_config_options("lp_level"),
            include_plotlyjs="cdn",
            auto_play=False,
        )


def read_pwt(pwt_version="pwt100"):
    """Read the penn world tables and add productivity column"""
    pwt = (
        pd.read_excel(RAW_DATA_DIR / f"{pwt_version}.xlsx", "Data")
        .assign(
            labor_productivity=lambda x: x["rgdpo"] / (x["emp"] * x["avh"])
        )
        .dropna(subset="labor_productivity")
    )
    return pwt


def select_relevant_data(
    pwt,
    key_countries=key_countries,
    key_years=[1945, 2019],
    columns=["year", "country", "labor_productivity", "avh"],
):
    """Filter the full PWT to rows for key_countries and key_years then select columns."""
    lp = (
        pwt[columns]
        .loc[
            lambda x: x["country"].isin(key_countries)
            & x["year"].between(*key_years)
        ]
        .reset_index(drop=True)
        .sort_values(  # So legend is ordered by final value.
            ["year", "labor_productivity", "country"], ascending=False
        )
    )
    return lp


def index_at_year(
    df, to_index="labor_productivity", at_year=1990, group_cols=["country"]
):
    """Adjust the series to_index in df so that it equals 100 at year."""
    return (
        df.merge(
            df.loc[lambda x: x["year"] == at_year, [*group_cols, to_index]],
            "left",
            group_cols,
            suffixes=("", "_base"),
            validate="many_to_one",
        )
        .assign(
            **{
                f"indexed_{to_index}": lambda x: 100
                * (x[to_index] / x[f"{to_index}_base"]),
                "index_year": at_year,
            }
        )
        .drop(columns=f"{to_index}_base")
    )


def add_plot_notes(fig, note, x=0, y="auto"):
    """Add note to bottome left of figure."""
    if isinstance(note, list):
        note = "<br>".join(note)
    if y == "auto":
        y = -0.15 - 0.05 * note.count("<br>")

    text_colour = fig.layout.template.layout.font.color
    fig.add_annotation(
        dict(
            x=x,
            y=y,
            xref="x domain",
            yref="y domain",
            text=note,
            showarrow=False,
            font=dict(size=12, color=text_colour),
            align="left",
        )
    )
    return fig


def formatted_line_plot(
    data,
    line_args,
    notes=data_source_note,
    notes_args={},
    shown_countries=["United States", "Germany", "Canada", "Japan"],
):
    """Plot and apply common styling to a plotly express line plot."""
    default_line_args = dict(
        x="year",
        y="indexed_labor_productivity",
        color="country",
        labels={
            "country": "Country",
            "year": "Year",
            "labor_productivity": "Labour Productivity",
            "indexed_labor_productivity": "Labor productivity growth",
            "index_year": "Base year",
        },
        color_discrete_map=country_palette,
    )
    line_args = default_line_args | line_args
    fig = (
        px.line(data, **line_args)
        .update_xaxes(title="")
        .update_yaxes(title="")
        .update_traces(line_width=3)
        .update_traces(
            selector=lambda t: t.name not in shown_countries,
            visible="legendonly",
        )
        .update_layout(legend_title="")
    )
    fig = add_plot_notes(fig, notes, **notes_args)
    return fig


def inset_legend_layout(x=0.02, y=0.99):
    """Get legend layout to inset legend in plot."""
    return dict(
        yanchor="top",
        y=y,
        xanchor="left",
        x=x,
        bordercolor=pt.colour["dark_grey"],
        borderwidth=2,
    )


def show(fig, key):
    """Show the plot with the custom config options."""
    fig[key].show(config=pt.get_config_options(key))


if __name__ == "__main__":
    main()
