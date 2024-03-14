import pandas as pd
import requests
from io import StringIO
import uuid

from tqdm import tqdm

import sys
import os
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_path)

from assets.cities import cities


class DataCollector:
    """
    A class for collecting football data from the https://www.football-data.co.uk.

    Attributes:
        league (str): The league for which data is collected ('serie_a' or 'epl').
        all_data (list): A list to store the collected data.

    Methods:
        collect_data(year_start, year_end, write_csv=False): Collects data for the specified years.
        _construct_url(year): Constructs the URL for the data based on the league and year.
        _process_data(write_csv): Processes the collected data and returns a DataFrame.
    """

    def __init__(self, league: str):
        """
        Initializes a DataCollector object.

        Args:
            league (str): The league for which data is collected ('serie_a' or 'epl').
        """
        self.league = league
        self.all_data = []

    def collect_data(self, year_start: int, year_end: int, write_csv=False):
        """
        Collects data for the specified years.

        Args:
            year_start (int): The starting year.
            year_end (int): The ending year.
            write_csv (bool, optional): Whether to write the collected data to a CSV file. Defaults to False.

        Returns:
            pandas.DataFrame: The processed data as a DataFrame.
        """
        for year in tqdm(range(year_start, year_end + 1), desc="Fetching data"):
            url = self._construct_url(year)
            try:
                r = requests.get(url)
                if r.status_code == 200:
                    data = StringIO(r.text)
                    df = pd.read_csv(data, on_bad_lines="skip")
                    self.all_data.append(df)
                else:
                    print(
                        f"Data for season {year}/{year+1} not found or could not be retrieved."
                    )
            except requests.RequestException as e:
                print(f"Request failed for season {year}/{year+1}: {e}")

        return self._process_data(write_csv)

    def _construct_url(self, year: int):
        """
        Constructs the URL for the data based on the league and year.

        Args:
            year (int): The year for which the URL is constructed.

        Returns:
            str: The constructed URL.
        
        Raises:
            ValueError: If the league is invalid.
        """
        if self.league == "serie_a":
            return f"https://www.football-data.co.uk/mmz4281/{str(year)[-2:]}{str(year+1)[-2:]}/I1.csv"
        elif self.league == "epl":
            return f"https://www.football-data.co.uk/mmz4281/{str(year)[-2:]}{str(year+1)[-2:]}/E0.csv"
        else:
            raise ValueError("Invalid league. Must be 'serie_a' or 'epl'.")

    def _process_data(self, write_csv: bool) -> pd.DataFrame:
        """
        Processes the collected data and returns a DataFrame.

        Args:
            write_csv (bool): Whether to write the processed data to a CSV file.

        Returns:
            pandas.DataFrame: The processed data as a DataFrame.
        """
        all_data_df = pd.concat(self.all_data, ignore_index=True)
        all_data_df = (
            all_data_df.assign(
                Div=self.league,
                Date=lambda x: pd.to_datetime(x['Date'], dayfirst=True),
                season=lambda x: [
                    f"{date.year}/{str(date.year + 1)}" if date.month >= 8 else f"{date.year - 1}/{date.year}"
                    for date in pd.to_datetime(x['Date'], dayfirst=True)
                ],
                game_id=[uuid.uuid4().hex[:8] for _ in range(len(all_data_df))],
                TG=all_data_df["FTHG"] + all_data_df["FTAG"],
                city_name=all_data_df["HomeTeam"].map(
                    lambda x: cities[x]["name"] if x in cities else None
                ),
                lat=all_data_df["HomeTeam"].map(
                    lambda x: cities[x]["lat"] if x in cities else None
                ),
                lon=all_data_df["HomeTeam"].map(
                    lambda x: cities[x]["lon"] if x in cities else None
                ),
            )
            .dropna(how="all", axis=1)
        )
        cols = (
            ["game_id"]
            + [col for col in all_data_df.columns if col not in ["game_id", "TG"]][:3]
            + ["TG"]
            + [
                col for col in all_data_df.columns if col not in ["game_id", "TG", "TG"]
            ][3:]
        )

        all_data_df = all_data_df[cols]
        if write_csv:
            filename = f"{self.league}.csv"
            all_data_df.to_csv(filename, index=False)
            print(f"Data written to {filename}")
        return all_data_df
    
    @staticmethod
    def compute_team_statistics(df):
            """
            Compute team statistics based on the given DataFrame.

            Parameters:
            - df (pandas.DataFrame): The DataFrame containing the football match data.

            Returns:
            - stats (pandas.DataFrame): The computed team statistics including home and away statistics, total statistics, and various ratios.
            """
            # Aggregate home and away statistics
            home_stats = df.groupby('HomeTeam').agg(HomeGames=('HomeTeam', 'count'), HomeWins=('FTR', lambda x: (x == 'H').sum()), HomeDraws=('FTR', lambda x: (x == 'D').sum()), HomeGoals=('FTHG', 'sum'))
            away_stats = df.groupby('AwayTeam').agg(AwayGames=('AwayTeam', 'count'), AwayWins=('FTR', lambda x: (x == 'A').sum()), AwayDraws=('FTR', lambda x: (x == 'D').sum()), AwayGoals=('FTAG', 'sum'))

            # Merge home and away statistics
            stats = home_stats.merge(away_stats, left_index=True, right_index=True, how='outer').fillna(0)

            # Calculate total statistics
            stats['TotalGames'] = stats['HomeGames'] + stats['AwayGames']
            stats['TotalWins'] = stats['HomeWins'] + stats['AwayWins']
            stats['TotalDraws'] = stats['HomeDraws'] + stats['AwayDraws']
            stats['TotalGoals'] = stats['HomeGoals'] + stats['AwayGoals']

            # Calculate ratios
            stats['WinRatio'] = stats['TotalWins'] / stats['TotalGames']
            stats['DrawRatio'] = stats['TotalDraws'] / stats['TotalGames']
            stats['HomeWinRatio'] = stats['HomeWins'] / stats['HomeGames']
            stats['AwayWinRatio'] = stats['AwayWins'] / stats['AwayGames']
            stats['HomeGoalRatio'] = stats['HomeGoals'] / stats['HomeGames']
            stats['AwayGoalRatio'] = stats['AwayGoals'] / stats['AwayGames']
            stats['TotalGoalRatio'] = stats['TotalGoals'] / stats['TotalGames']

            return stats.reset_index().rename(columns={'index': 'Team'})

if __name__ == "__main__":
    # example usage
    dc = DataCollector(league="serie_a")
    data = dc.collect_data(2003, 2023, write_csv=False)
    # sample output
    teams_stats = dc.compute_team_statistics(data)

    print(teams_stats.head())

