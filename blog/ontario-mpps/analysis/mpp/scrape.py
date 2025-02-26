"""Scrape the raw data from the OLA website and save to RAW_DATA_DIR"""

from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger
from mpp.config import INTERIM_DATA_DIR, OLA_URL, RAW_DATA_DIR, REQUEST_HEADERS
from tqdm import tqdm

tqdm.pandas()


def get_parliaments():
    """Get the data for each parliament."""
    parliaments_url = f"{OLA_URL}/en/members/all"
    parliaments_df = (
        pd.read_html(
            parliaments_url,
            storage_options=REQUEST_HEADERS,
            extract_links="all",
        )[0]
        .rename(columns=lambda x: x[0])
        .assign(
            Start=lambda x: pd.to_datetime(
                x["Start"].str[0], format="%B %d, %Y"
            ),
            End=lambda x: pd.to_datetime(x["End"].str[0], format="%B %d, %Y"),
            ParliamentLink=lambda x: x["Parliament"].str[1],
            Parliament=lambda x: x["Parliament"]
            .str[0]
            .str.extract(r"(\d+)")
            .astype(int),
        )
    )
    parliaments_df.to_parquet(INTERIM_DATA_DIR / "parliaments.parquet")


def get_members_by_parliament(
    parliaments_path: Path = (INTERIM_DATA_DIR / "parliaments.parquet"),
):
    """Get the names of MPPs who served in each parliament using the links from parliaments.parquet"""
    parliaments = pd.read_parquet(parliaments_path)

    def scrape_parliament_members(
        parliament_link: str, parliament_number: int
    ):
        return (
            pd.read_html(
                f"{OLA_URL}/{parliament_link}",
                storage_options=REQUEST_HEADERS,
                extract_links="all",
            )[0]
            .rename(columns=lambda x: x[0])
            .assign(
                Riding=lambda x: x["Riding"].str[0],
                Parliament=parliament_number,
                Name=lambda x: x["MPP"].str[0],
                NameLink=lambda x: x["MPP"].str[1],
            )
            .drop(columns="MPP")
        )

    parliament_members = pd.concat(
        parliaments[["ParliamentLink", "Parliament"]]
        .progress_apply(
            lambda x: scrape_parliament_members(
                x["ParliamentLink"], x["Parliament"]
            ),
            axis=1,
        )
        .to_list()
    )
    parliament_members.to_parquet(
        INTERIM_DATA_DIR / "parliament_members.parquet"
    )


def get_all_member_info(
    members_path: Path = INTERIM_DATA_DIR / "parliament_members.parquet",
):
    """Scrape the member info page for each member to get data on each members terms, memberships, and party affiliation."""
    members = pd.read_parquet(members_path)
    ridings = []
    positions = []
    parties = []
    for _, member_link in tqdm(members["NameLink"].drop_duplicates().items()):
        mpp_ridings, mpp_positions, mpp_parties = scrape_member_profile(
            member_link
        )
        ridings.append(mpp_ridings)
        positions.append(mpp_positions)
        parties.append(mpp_parties)

    ridings_df = pd.concat(ridings).assign(
        Start=lambda x: pd.to_datetime(x["Start"], format="%B %d, %Y"),
        End=lambda x: pd.to_datetime(x["End"], format="%B %d, %Y"),
        Parliament=lambda x: x["Parliament"].str.extract(r"(\d+)").astype(int),
    )
    positions_df = pd.concat(positions).assign(
        Start=lambda x: pd.to_datetime(x["Start"], format="%B %d, %Y"),
        End=lambda x: pd.to_datetime(x["End"], format="%B %d, %Y"),
        Parliament=lambda x: x["Parliament"].str.extract(r"(\d+)").astype(int),
    )
    parties_df = pd.concat(parties).assign(
        Start=lambda x: pd.to_datetime(x["Start"], format="%B %d, %Y"),
        End=lambda x: pd.to_datetime(x["End"], format="%B %d, %Y"),
    )

    ridings_df.to_parquet(INTERIM_DATA_DIR / "member_ridings.parquet")
    positions_df.to_parquet(INTERIM_DATA_DIR / "member_positions.parquet")
    parties_df.to_parquet(INTERIM_DATA_DIR / "member_parties.parquet")


def scrape_member_profile(
    member_link: str,
    cache_dir: Path = RAW_DATA_DIR / "member_profiles",
):
    """Scrape an individual MPP's info from their profile page."""
    member_name = f"{member_link.replace('/en/members/all/', '')}"
    soup = get_soup_from_cache(cache_dir, member_link, member_name)

    mpptabs_content = soup.find("div", class_="mpptabscontent-region")
    sections = mpptabs_content.find_all("div", class_="row")
    data = {}
    for sec in sections:
        sec_header = sec.find("h3", class_="accordion-header")
        if not sec_header:
            continue
        sec_name = sec_header.get_text(strip=True)
        sec_data = sec.find("div", class_="accordion-body")

        # This uses a fairly messy in-place approach,
        # blame the OLA's lack of hierarchy.

        data[sec_name] = []
        if sec_name == "Riding representation":
            scrape_riding_representation(data, sec_name, sec_data, member_name)
        elif sec_name == "Career details":
            scrape_career_details(data, sec_name, sec_data, member_name)
        elif sec_name == "Party affiliation(s)":
            scrape_party_affiliations(data, sec_name, sec_data, member_name)
        elif sec_name == "In memoriam":
            # Contains DOB, DOD and a link to a biography.
            # No need to collect for our analysis.
            continue
        else:
            logger.warning(
                f"Scrape procedure for section `{sec_name}` has not been implemented."
            )
    ridings = pd.DataFrame(
        data.get("Riding representation", []),
        columns=["Name", "Riding", "Parliament", "Start", "End"],
    )
    memberships = pd.DataFrame(
        data.get("Career details", []),
        columns=["Name", "Parliament", "Position", "Start", "End"],
    )
    parties = pd.DataFrame(
        data.get("Party affiliation(s)", []),
        columns=["Name", "Party", "Start", "End"],
    )
    return ridings, memberships, parties


def scrape_party_affiliations(data, sec_name, sec_data, member_name):
    """Scrape the party affiliation section of the member profile page."""
    sec_rows = sec_data.find_all("div", class_="views-row")
    for row in sec_rows:
        data[sec_name].append(
            [
                member_name,
                *[s for s in list(row.find("p").stripped_strings) if s != "–"],
            ]
        )


def scrape_career_details(data, sec_name, sec_data, member_name):
    """Scrape the career details section of the member profile page."""
    sec_row = {
        "Name": member_name,
        "Parliament": "",
        "Position": "",
        "Start": "",
        "End": "",
    }
    for s in list(sec_data.stripped_strings):
        if s == "–":
            continue
        elif " Parliament (" in s:
            sec_row["Parliament"] = s
        elif pd.to_datetime(s, "coerce", format="%B %d, %Y") is not pd.NaT:
            if sec_row["Start"]:
                sec_row["End"] = s
                data[sec_name].append(
                    [
                        sec_row["Name"],
                        sec_row["Parliament"],
                        sec_row["Position"],
                        sec_row["Start"],
                        sec_row["End"],
                    ]
                )
                sec_row["Position"] = ""
                sec_row["Start"] = ""
                sec_row["End"] = ""
            else:
                sec_row["Start"] = s
        else:
            sec_row["Position"] = s


def scrape_riding_representation(data, sec_name, sec_data, member_name):
    """Scrape the riding representation section of the member profile page."""
    sec_row = {
        "Name": member_name,
        "Riding": "",
        "Parliament": "",
        "Start": "",
        "End": "",
    }
    for s in list(sec_data.stripped_strings):
        if s == "–":
            continue
        elif "Parliament" in s:
            sec_row["Parliament"] = s
        elif pd.to_datetime(s, "coerce", format="%B %d, %Y") is not pd.NaT:
            if sec_row["Start"]:
                sec_row["End"] = s
                data[sec_name].append(
                    [
                        sec_row["Name"],
                        sec_row["Riding"],
                        sec_row["Parliament"],
                        sec_row["Start"],
                        sec_row["End"],
                    ]
                )
                sec_row["Start"] = ""
                sec_row["End"] = ""
            else:
                sec_row["Start"] = s
        else:
            sec_row["Riding"] = s


def get_soup_from_cache(cache_dir: Path, link: str, name: str):
    """Get the soup either from the cache, if it has been cached, or by a request."""
    cache_path = cache_dir / f"{name}.html"
    if cache_path.exists():
        with open(cache_path) as fp:
            soup = BeautifulSoup(fp, "html.parser")
    elif link is None:
        logger.warning(
            f"{name} missing from {cache_dir} and no link provided. Returning empty soup."
        )
        soup = BeautifulSoup("", "html.parser")
    else:
        logger.info(f"Getting response from {OLA_URL}/{link}")
        response = requests.get(f"{OLA_URL}/{link}", headers=REQUEST_HEADERS)
        if response.status_code != 200:
            raise ValueError(f"Response to {link} failed.")
        with open(cache_path, "wb") as f:
            f.write(response.content)
        soup = BeautifulSoup(response.content, "html.parser")
    return soup


def get_hansards(hansard_list_link="/en/legislative-business/house-documents"):
    """Scrape Hansard records for each parliament"""
    # First get the list of links to each parliament's documents
    soup_parliaments_list = get_soup_from_cache(
        RAW_DATA_DIR / "hansard", hansard_list_link, "all_documents"
    )
    all_sessions_header = soup_parliaments_list.find(
        "h2", string="All House documents"
    )
    all_sessions_list = all_sessions_header.find_parent(
        "div", class_="contextual-region"
    )
    sessions_links_list = [
        a.get("href").replace(OLA_URL, "")
        for a in all_sessions_list.find_all("a")
    ]

    # Second for each parliament's documents scrape all available documents
    doc_links_list = []
    for session_link in sessions_links_list:
        session_name = "_".join(session_link.split("/")[-3:-1])
        soup_session_page = get_soup_from_cache(
            RAW_DATA_DIR / "hansard", session_link, session_name
        )
        all_session_docs = soup_session_page.find(
            "div", class_="view-house-documents"
        )
        session_doc_links_list = [
            a.get("href").replace(OLA_URL, "")
            for a in all_session_docs.find_all("a")
        ]
        doc_links_list.extend(session_doc_links_list)
    doc_links = pd.DataFrame(doc_links_list, columns=["DocLink"]).assign(
        Volume=lambda x: x["DocLink"].str.split("/").str[-1]
    )
    # Add a link to the first volume where two volumes are available.
    doc_links = pd.concat(
        [
            doc_links,
            doc_links[lambda x: x["Volume"] == "hansard-1"].assign(
                DocLink=lambda x: x["DocLink"].replace(
                    {"hansard-1": "hansard"}, regex=True
                ),
                Volume="hansard",
            ),
        ]
    ).sort_values("DocLink", ascending=False)

    # Third scrape each available doc and extract votes.
    for _, doc_link in doc_links["DocLink"].items():
        doc_name = "_".join(doc_link.split("/")[-4:])
        soup_session_page = get_soup_from_cache(
            RAW_DATA_DIR / "hansard", doc_link, doc_name
        )


def parse_hansards_to_dfs(
    hansard_cache_dir: Path = RAW_DATA_DIR / "hansard",
    output_dir=INTERIM_DATA_DIR,
):
    """Parse each hansard file to dataframes."""
    # Initialize outer list to store all rows and inner dict to store current context
    speech_data = []
    procedure_data = []
    vote_data = []
    context = {
        "date": "",
        "time": "",
        "section": "",
        "topic": "",
        "speaker": "",
        "speech": "",
        "procedure": "",
        "voter": "",
        "vote": "",
    }

    # Define keys from columns to include in each outer list
    # These are the columns for the final dataframe.
    speech_columns = ["date", "time", "section", "topic", "speaker", "speech"]  # fmt: skip
    procedure_columns = ["date", "time", "section", "topic", "procedure"]  # fmt: skip
    vote_columns = ["date", "time", "section", "topic", "voter", "vote"]
    for file in tqdm(sorted(hansard_cache_dir.iterdir())):
        if not file.name.endswith(("hansard.html", "hansard-1.html")):
            # ignore non-transcripts
            continue
        file_date = file.stem.split("_")[2]
        if pd.to_datetime(file_date) <= pd.to_datetime("1984-05-11"):
            continue
        soup = get_soup_from_cache(hansard_cache_dir, None, file.stem)
        transcript_date = soup.find("time").get_text(strip=True)
        # Reset context if not a second volume.
        if "-1" in file.stem:
            context["date"] = transcript_date
        else:
            context = {
                "date": transcript_date,
                "time": "",
                "section": "",
                "topic": "",
                "speaker": "",
                "speech": "",
                "procedure": "",
                "voter": "",
                "vote": "",
            }

        # Iterate over every tag of the transcript and keep track of the current context.
        transcript_soup = soup.find("div", id="transcript")
        if transcript_soup is None:
            # logger.warning(f"No transcript div in {file.name}. Skipping.")
            continue
        for el in transcript_soup.children:
            el_tag = el.name
            if not el_tag:
                continue  # if text or comment rather than tag
            el_classes = el.get("class")
            if el_tag == "h2":
                if context["speaker"] and context["speech"]:
                    speech_data.append(get_from_dict(context, speech_columns))
                    context["speaker"] = context["speech"] = ""
                context["section"] = el.get_text()
            elif el_tag == "h3":
                if context["speaker"] and context["speech"]:
                    speech_data.append(get_from_dict(context, speech_columns))
                    context["speaker"] = context["speech"] = ""
                context["topic"] = el.get_text()
            elif el_tag == "h4" and "voteDirection" in el_classes:
                context["vote"] = el.get_text()
            elif el_tag == "ul":
                context["voter"] = [
                    # Get a list of each voter in the ul tag.
                    # Will explode later to individual rows for each voter.
                    v.get_text()
                    for v in el.find_all("li", class_="voteText")
                ]
                vote_data.append(get_from_dict(context, vote_columns))
            elif el_tag == "p" and not el_classes:
                context["speech"] += "\n" + el.get_text()
            elif el_tag == "p" and "speakerStart" in el_classes:
                if context["speaker"] and context["speech"]:
                    speech_data.append(get_from_dict(context, speech_columns))
                    context["speaker"] = context["speech"] = ""
                speaker = el.find("strong")
                if not speaker:  # treat as a new paragraph
                    context["speech"] += "\n" + el.get_text()
                    continue
                context["speaker"] = speaker.get_text()
                speaker.decompose()  # remove speaker from element.
                context["speech"] = el.get_text()
            elif el_tag == "p" and "procedure" in el_classes:
                after_el = el.find_next_siblings()
                # If is the last procedure in the transcript (the end of session)
                if len(after_el) < 20 and not any(
                    [p.get_text() for p in after_el]
                ):
                    speech_data.append(get_from_dict(context, speech_columns))
                context["procedure"] = el.get_text()
                procedure_data.append(
                    get_from_dict(context, procedure_columns)
                )
            elif el_tag == "p" and "timeStamp" in el_classes:
                context["time"] = el.get_text()
    speech_df = pd.DataFrame(speech_data, columns=speech_columns)
    procedure_df = pd.DataFrame(procedure_data, columns=procedure_columns)
    vote_df = pd.DataFrame(vote_data, columns=vote_columns).explode("voter")

    speech_df.to_parquet(output_dir / "speeches.parquet")
    procedure_df.to_parquet(output_dir / "procedures.parquet")
    vote_df.to_parquet(output_dir / "votes.parquet")


def get_from_dict(dictionary, keys):
    """Helper function to get desired keys from the context dictionary."""
    return [dictionary[key] for key in keys]


if __name__ == "__main__":
    # get_parliaments()
    # get_members_by_parliament()
    # get_all_member_info()
    # get_hansards()
    parse_hansards_to_dfs()

    # import os
    # os.chdir("./blog/ontario-mpps/analysis/")
    # from mpp.scrape import *
    # TODO scrape expense disclosures from  https://www.ola.org/en/members/expense-disclosure/list
    # TODO scrape leader expense disclosures from https://www.ola.org/en/members/expense-disclosure/official-opposition
