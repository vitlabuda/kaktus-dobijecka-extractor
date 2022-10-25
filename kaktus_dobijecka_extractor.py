#!/usr/bin/env python3

# Copyright (c) 2022 Vít Labuda. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#  1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
#     disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
#     following disclaimer in the documentation and/or other materials provided with the distribution.
#  3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
#     products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from __future__ import annotations
from typing import final, Final, Optional, TypeVar, Sequence, Union, Any
import dataclasses
import sys
import os.path
import re
import datetime
import csv
import json
import unicodedata
import requests
import bs4


@final
class Settings:
    DEFAULT_OUTPUT_DIR: Final[str] = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")

    OUTPUT_JSON_FILENAME: Final[str] = "dobijecka_data.json"
    OUTPUT_JSON_INDENT: Final[Optional[int]] = 4

    OUTPUT_CSV_FILENAME: Final[str] = "dobijecka_data.csv"
    OUTPUT_CSV_FORMAT_PARAMS: Final[dict[str, Any]] = {
       "delimiter": ",",
       "quotechar": "\"",
       "quoting": csv.QUOTE_ALL
    }

    KAKTUS_DOBIJECKA_NEWS_SOURCES: Final[tuple[tuple[str, datetime.date], ...]] = (
        ("https://www.mujkaktus.cz/novinky", datetime.date.today()),
        ("https://web.archive.org/web/20220524091831/https://www.mujkaktus.cz/novinky", datetime.date(2022, 5, 24)),
        ("https://web.archive.org/web/20200925041028/https://www.mujkaktus.cz/novinky", datetime.date(2020, 9, 25)),
        ("https://web.archive.org/web/20200815101625/https://www.mujkaktus.cz/novinky", datetime.date(2020, 8, 15)),
    )


class DobijeckaExtractionError(Exception):
    def __init__(self, error_message: str):
        Exception.__init__(self, error_message)


CheckNone_T = TypeVar("CheckNone_T")
CheckEmpty_T = TypeVar("CheckEmpty_T", bound=Sequence)


@dataclasses.dataclass(frozen=True)
class DobijeckaData:
    date: datetime.date
    hour_begin: int
    hour_end: int
    title: str
    description: str

    def do_datetime_data_match(self, other: DobijeckaData) -> bool:
        return (self.date == other.date and
                self.hour_begin == other.hour_begin and
                self.hour_end == other.hour_end)

    def to_serializable_tuple(self) -> tuple[str, int, int, str, str]:
        return str(self.date), self.hour_begin, self.hour_end, self.title, self.description

    def to_serializable_dict(self) -> dict[str, Union[str, int]]:
        return {
            "date": str(self.date),
            "hour_begin": self.hour_begin,
            "hour_end": self.hour_end,
            "title": self.title,
            "description": self.description
        }


def info(*args, separate_by: str = "") -> None:
    if separate_by:
        assert len(separate_by) == 1

        info(separate_by * 100, separate_by="")
        info(*args, separate_by="")
        info(separate_by * 100, separate_by="")
    else:
        print("[INFO]", *args)


def check_none(variable: Optional[CheckNone_T], error_message: str) -> CheckNone_T:
    if variable is None:
        raise DobijeckaExtractionError(error_message)

    return variable


def check_empty(variable: CheckEmpty_T, error_message: str) -> CheckEmpty_T:
    if len(variable) == 0:
        raise DobijeckaExtractionError(error_message)

    return variable


def unify_control_characters_and_whitespace(input_string: str) -> str:
    input_string = "".join(
        (" " if unicodedata.category(char)[0] in ("C", "Z") else char)
        for char in input_string
    )

    return re.sub(r'\s+', ' ', input_string).strip()


def main() -> None:
    output_dir_path = get_output_dir_path()

    aggregated_dobijecka_data = get_aggregated_dobijecka_data()

    save_dobijecka_data(aggregated_dobijecka_data, output_dir_path)


def get_output_dir_path() -> str:
    try:
        output_dir_path = sys.argv[1]
    except IndexError:
        output_dir_path = Settings.DEFAULT_OUTPUT_DIR

    info(f"Output directory path: {output_dir_path}", separate_by="x")
    return output_dir_path


def get_aggregated_dobijecka_data() -> list[DobijeckaData]:
    date_dobijecka_data_pairs = {}

    for url, base_date in Settings.KAKTUS_DOBIJECKA_NEWS_SOURCES:
        for dobijecka_data in parse_dobijecka_data_from_html(download_url(url), base_date):
            if dobijecka_data.date in date_dobijecka_data_pairs:
                # The webpages may "overlap" - they may contain 'Dobíječka' announcements which have already been
                #  extracted from previous webpages, but their content should not be different in any way!
                previously_extracted_dobijecka_data = date_dobijecka_data_pairs[dobijecka_data.date]
                if not dobijecka_data.do_datetime_data_match(previously_extracted_dobijecka_data):
                    raise DobijeckaExtractionError(f"The following two 'Dobíječka' announcements from the same date differ: {dobijecka_data!r} != {previously_extracted_dobijecka_data!r}")
            else:
                date_dobijecka_data_pairs[dobijecka_data.date] = dobijecka_data

    if not date_dobijecka_data_pairs:
        raise DobijeckaExtractionError("No 'Dobíječka' announcements could be extracted!")

    info(f"A total of {len(date_dobijecka_data_pairs)} 'Dobíječka' announcements have been extracted from all the URLs.", separate_by="!")
    return sorted(date_dobijecka_data_pairs.values(), key=lambda item: item.date, reverse=True)


def download_url(url: str) -> str:
    info(f"Downloading {url!r}...", separate_by="-")

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DobijeckaExtractionError(f"Failed to download {url!r}: {e}")

    return response.text


def parse_dobijecka_data_from_html(html_string: str, base_date: datetime.date) -> list[DobijeckaData]:
    dobijecka_data_list = []

    html_doc = bs4.BeautifulSoup(html_string, "html.parser")

    article_elems = check_empty(html_doc.find_all("div", class_="journal-content-article"), "Could not find any 'news articles' in the HTML!")
    for article_elem in article_elems:
        # Title
        title = extract_title_from_article_elem(article_elem)

        # Description
        description = extract_description_from_article_elem(article_elem)

        # Date, begin & end hour
        datetime_data = parse_datetime_data_from_dobijecka_title_or_description(title, description, base_date)
        if datetime_data is None:
            info(f"This 'news article' does not seem to be a 'Dobíječka' announcement: {title!r} --- {description!r}")
            continue

        date, hour_begin, hour_end = datetime_data
        dobijecka_data_list.append(DobijeckaData(date=date, hour_begin=hour_begin, hour_end=hour_end, title=title, description=description))

        if date > base_date:
            raise DobijeckaExtractionError(f"The 'Dobíječka' announcements are not parsed in retrospective order! (date: {date}, base date: {base_date})")
        base_date = date  # The date extracted from this 'news article' will be the base date for the next 'article'...

    if not dobijecka_data_list:
        raise DobijeckaExtractionError(f"Even though {len(article_elems)} 'news articles' have been found in the HTML, none of them could be parsed...")

    info(f"{len(dobijecka_data_list)} 'Dobíječka' announcements have been found in the HTML.", separate_by="-")
    return dobijecka_data_list


def extract_title_from_article_elem(article_elem: bs4.Tag) -> str:
    title_elem = check_none(article_elem.find("h3"), "Could not find a title in the 'news article'!")
    title_text = title_elem.get_text()

    return unify_control_characters_and_whitespace(title_text)


def extract_description_from_article_elem(article_elem: bs4.Tag) -> str:
    description_elem = check_none(article_elem.find("p"), "Could not find a description in the 'news article'!")
    description_text = re.sub(r'Sdílet\s+na\s+Facebooku', '', description_elem.get_text(), flags=re.IGNORECASE)

    return unify_control_characters_and_whitespace(description_text)


# Returns 'None' if it appears that the "news article" is not about "Dobíječka"
def parse_datetime_data_from_dobijecka_title_or_description(title: str, description: str, base_date: datetime.date) -> Optional[tuple[datetime.date, int, int]]:  # (date, begin hour, end hour)
    # Date
    if (date := parse_date_from_dobijecka_description(description, base_date)) is None:
        return None

    # Begin & end hour - in the description in most cases, but very rarely in the title
    if (begin_end_hour := parse_begin_end_hour_from_dobijecka_title_or_description(title, description)) is None:
        return None

    return date, begin_end_hour[0], begin_end_hour[1]


# Returns 'None' if it appears that the "news article" is not about "Dobíječka"
def parse_date_from_dobijecka_description(description: str, base_date: datetime.date) -> Optional[datetime.date]:
    if not (date_match := re.search(r'(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})?', description)):
        return None

    date_day, date_month = int(date_match[1]), int(date_match[2])
    if date_match[3]:
        date_year = int(date_match[3])
    elif date_month > base_date.month:  # "Roll back" to previous year...
        date_year = base_date.year - 1
    else:
        date_year = base_date.year

    return datetime.date(date_year, date_month, date_day)


# Returns 'None' if it appears that the "news article" is not about "Dobíječka"
def parse_begin_end_hour_from_dobijecka_title_or_description(title: str, description: str) -> Optional[tuple[int, int]]:  # (begin hour, end hour)
    # This is a QUIRK for "Stačí si dneska 23. 11. mezi pátou a osmou hodinou dobít..."
    if "mezi pátou a osmou" in description:
        return 17, 20

    # This is a QUIRK for "... Mám tu dneska 9. 10. 2018 NEJdelší dobíječku ever - od 10 ráno do 10 večer. ..."
    if "od 10 ráno do 10 večer" in description:
        return 10, 22

    for pattern in (
            r'(?:mezi|v\s+čase)\s+(\d{1,2})[.:]00\s+až?\s+(\d{1,2})[.:]00',
            r'(?:mezi|v\s+čase)\s+(\d{1,2})\.?\s+až?\s+(\d{1,2})\.?',
            r'od\s+(\d{1,2})[.:]00\s+do\s+(\d{1,2})[.:]00',
            r'od\s+(\d{1,2})\.?\s+do\s+(\d{1,2})\.?(?!\s+stovek)',
    ):
        for source in (title, description):
            if begin_end_hour_match := re.search(pattern, source, flags=re.IGNORECASE):
                return int(begin_end_hour_match[1]), int(begin_end_hour_match[2])

    return None


def save_dobijecka_data(aggregated_dobijecka_data: list[DobijeckaData], output_dir_path: str) -> None:
    os.makedirs(output_dir_path, exist_ok=True)

    for save_fn, filepath in (
        (save_dobijecka_data_to_csv, os.path.join(output_dir_path, Settings.OUTPUT_CSV_FILENAME)),
        (save_dobijecka_data_to_json, os.path.join(output_dir_path, Settings.OUTPUT_JSON_FILENAME)),
    ):
        info(f"Saving the data using {save_fn.__name__!r} to {filepath!r}...", separate_by="x")
        save_fn(aggregated_dobijecka_data, filepath)


def save_dobijecka_data_to_csv(aggregated_dobijecka_data: list[DobijeckaData], filepath: str) -> None:
    assert aggregated_dobijecka_data

    with open(filepath, "w", encoding="utf-8") as file:
        csv_writer = csv.writer(file, **Settings.OUTPUT_CSV_FORMAT_PARAMS)

        csv_writer.writerow(field.name for field in dataclasses.fields(aggregated_dobijecka_data[0]))
        csv_writer.writerows(item.to_serializable_tuple() for item in aggregated_dobijecka_data)


def save_dobijecka_data_to_json(aggregated_dobijecka_data: list[DobijeckaData], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump([item.to_serializable_dict() for item in aggregated_dobijecka_data], file, indent=Settings.OUTPUT_JSON_INDENT)


if __name__ == '__main__':
    main()
