import pandas as pd
from logging import getLogger

from pycontrails import Flight

from lib.schemas import SpireWaypointPositional

logger = getLogger()


class ResampleHandler:
    """
    Handles interpolation & data model coercing for a sequence of waypoints for a flight instance.
    This handler takes:
     (A) a sample of waypoints within a closed time window, and
     (B) 1 or 2 waypoints** at some time prior to (A) (cached waypoints)
         (**these are the waypoints from the right-hand-side of the previous window)

     BB......................A.AA.AAA

    Work includes:
    - intra-window interpolation; i.e. interpolation within the window (A)
    - inter-window interpolation; i.e. backward interpolation between A_0 and B
    """

    FLIGHT_LEVELS = [
        200,
        210,
        220,
        230,
        240,
        250,
        260,
        270,
        280,
        290,
        300,
        310,
        320,
        330,
        340,
        350,
        360,
        370,
        380,
        390,
        400,
        410,
        420,
        430,
        440,
    ]

    def __init__(
        self,
        cache: list[SpireWaypointPositional],
        records_window: list[SpireWaypointPositional],
    ):
        """
        Parameters
        ----------
        cache
            one or two waypoints that are retrieved from cache -- historical records
        records_window
            a series of waypoints, belonging to a time window,
            delivered from a windowed batch stream (temporally contiguous) -- present records
        """
        self._waypoints_df_resampled: pd.DataFrame | None = None

        # column names as expected by Flight (pycontrails.core.flight)
        pycontrails_name_map = {"altitude_baro": "altitude_ft", "timestamp": "time"}

        df_cached = pd.DataFrame(cache)
        if not df_cached.empty:
            df_cached.rename(columns=pycontrails_name_map, inplace=True)
            # note: pycontrails resample_and_fill returns df w/ naive timestamps, hence:
            df_cached["time"] = pd.to_datetime(df_cached["time"]).apply(
                lambda r: r.tz_localize(None)
            )
            self._max_cache_ts = df_cached["time"].max()
        else:
            self._max_cache_ts = pd.to_datetime("1970")

        df_records = pd.DataFrame(records_window)
        df_records.rename(
            columns={"altitude_baro": "altitude_ft", "timestamp": "time"}, inplace=True
        )
        df_records["time"] = pd.to_datetime(df_records["time"]).apply(
            lambda r: r.tz_localize(None)
        )

        if df_records["time"].duplicated().sum():
            logger.warning("duplicated waypoints found in cache+records.")
            df_records.drop_duplicates(["time"], inplace=True)

        self._min_records_ts = df_records["time"].min()

        self._waypoints_df = pd.concat([df_cached, df_records])

    def interpolate(self):
        """
        Run minute interpolation within the records time window, and backwards between
        the first index of the records time window and the cached waypoints.
        """
        pyc_flight = Flight(self._waypoints_df)
        flight_resampled: pd.DataFrame = pyc_flight.resample_and_fill().dataframe

        # add imputation flags
        flight_resampled["imputed"] = True
        is_cached = flight_resampled["time"] <= self._max_cache_ts
        is_records_window = flight_resampled["time"] >= self._min_records_ts
        flight_resampled.loc[(is_cached | is_records_window), "imputed"] = False

        # compute the altitude_ft from altitude (note: pycontrails Flight operates on altitude [m])
        flight_resampled.loc[:, "altitude_ft"] = (
            flight_resampled["altitude"] * 3.28
        ).astype(int)

        flight_resampled["flight_level"] = flight_resampled["altitude_ft"].apply(
            self.altitude_ft_to_flight_level
        )

        # flight_resampled at this point will include minute data
        # the first row will match what was pulled from cache
        # the last row will have a timestamp that is the bottom of the minute
        # for the right-most minutes data in the spire waypoints record window ingested from pubsub
        # -------------------

        # Cleanup
        flight_resampled.drop(columns=["altitude"], inplace=True)

        self._waypoints_df_resampled = flight_resampled
        return self

    @property
    def waypoints_resampled(self) -> list[SpireWaypointPositional]:
        """
        Returns
        -------
        List of SpireWaypointPositional objects, representing the resampled waypoints
        between the cached waypoints and the records waypoints passed to this handler.
        """
        if not isinstance(self._waypoints_df_resampled, pd.DataFrame):
            raise ValueError(
                "interpolate() must be run before fetching the resampled waypoints."
            )

        waypoints: list[SpireWaypointPositional] = []
        for _, r in self._waypoints_df_resampled.iterrows():
            wp = SpireWaypointPositional(
                ingestion_time=None,
                timestamp=r["time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                latitude=r["latitude"],
                longitude=r["longitude"],
                collection_type=None,
                altitude_baro=r["altitude_ft"],
                imputed=r["imputed"],
                flight_level=r["flight_level"],
            )
            waypoints.append(wp)
        return waypoints

    @classmethod
    def altitude_ft_to_flight_level(cls, alt_ft: int):
        """
        Converts altitude in feet MSL to flight level (100s of ft), snapped to the nearest level.
        """
        if alt_ft < (cls.FLIGHT_LEVELS[0] * 100) - 500:
            return -999
        diff = lambda i: abs(cls.FLIGHT_LEVELS[i] - alt_ft // 100)  # noqa:E731
        min_ix = min(range(len(cls.FLIGHT_LEVELS)), key=diff)
        return cls.FLIGHT_LEVELS[min_ix]
