from datetime import datetime
from logging import Logger, getLogger
from pprint import pprint
from typing import Optional

# The arrow library is used to handle datetimes
import arrow
from requests import Session

US_PROXY = "https://us-ca-proxy-jfnx5klx2a-uw.a.run.app"
HOST_PARAM = "?host=https://hydroquebec.com"
DATA_PATH = "data/documents-donnees/donnees-ouvertes/json"
PRODUCTION_URL = f"{US_PROXY}/{DATA_PATH}/production.json{HOST_PARAM}"
CONSUMPTION_URL = f"{US_PROXY}/{DATA_PATH}/demande.json{HOST_PARAM}"
# Reluctant to call it 'timezone', since we are importing 'timezone' from datetime
timezone_id = "America/Montreal"


def fetch_production(
    zone_key: str = "CA-QC",
    session: Optional[Session] = None,
    target_datetime: Optional[datetime] = None,
    logger: Logger = getLogger(__name__),
) -> list:
    """Requests the last known production mix (in MW) of a given region.
    In this particular case, translated mapping of JSON keys are also required"""

    def if_exists(elem: dict, etype: str):

        english = {
            "hydraulique": "hydro",
            "thermique": "thermal",
            "solaire": "solar",
            "eolien": "wind",
            # autres is all renewable, and mostly biomass.  See Github    #3218
            "autres": "biomass",
            "valeurs": "values",
        }
        english = {v: k for k, v in english.items()}
        try:
            return elem["valeurs"][english[etype]]
        except KeyError:
            return 0.0

    data = _fetch_quebec_production(session)
    list_res = []
    for elem in reversed(data["details"]):
        if elem["valeurs"]["total"] != 0:
            list_res.append(
                {
                    "zoneKey": zone_key,
                    "datetime": arrow.get(elem["date"], tzinfo=timezone_id).datetime,
                    "production": {
                        "biomass": if_exists(elem, "biomass"),
                        "coal": 0.0,
                        "hydro": if_exists(elem, "hydro"),
                        "nuclear": 0.0,
                        "oil": 0.0,
                        "solar": if_exists(elem, "solar"),
                        "wind": if_exists(elem, "wind"),
                        # See Github issue #3218, Québec's thermal generation is at Bécancour gas turbine.
                        # It is reported with a delay, and data source returning 0.0 can indicate either no generation or not-yet-reported generation.
                        # Thus, if value is 0.0, overwrite it to None, so that backend can know this is not entirely reliable and might be updated later.
                        "gas": if_exists(elem, "thermal") or None,
                        # There are no geothermal electricity generation stations in Québec (and all of Canada for that matter).
                        "geothermal": 0.0,
                        "unknown": if_exists(elem, "unknown"),
                    },
                    "source": "hydroquebec.com",
                }
            )
    return list_res


def fetch_consumption(
    zone_key: str = "CA-QC",
    session: Optional[Session] = None,
    target_datetime: Optional[datetime] = None,
    logger: Logger = getLogger(__name__),
):
    data = _fetch_quebec_consumption(session)
    list_res = []
    for elem in reversed(data["details"]):
        if "demandeTotal" in elem["valeurs"]:
            list_res.append(
                {
                    "zoneKey": zone_key,
                    "datetime": arrow.get(elem["date"], tzinfo=timezone_id).datetime,
                    "consumption": elem["valeurs"]["demandeTotal"],
                    "source": "hydroquebec.com",
                }
            )
    return list_res


def _fetch_quebec_production(
    session: Optional[Session] = None, logger: Logger = getLogger(__name__)
) -> str:
    s = session or Session()
    response = s.get(PRODUCTION_URL)

    if not response.ok:
        logger.info(
            "CA-QC: failed getting requested production data from hydroquebec - URL {}".format(
                PRODUCTION_URL
            )
        )
    return response.json()


def _fetch_quebec_consumption(
    session: Optional[Session] = None, logger: Logger = getLogger(__name__)
) -> str:
    s = session or Session()
    response = s.get(CONSUMPTION_URL)

    if not response.ok:
        logger.info(
            "CA-QC: failed getting requested consumption data from hydroquebec - URL {}".format(
                CONSUMPTION_URL
            )
        )
    return response.json()


if __name__ == "__main__":
    """Main method, never used by the Electricity Map backend, but handy for testing."""

    test_logger = getLogger()

    print("fetch_production() ->")
    pprint(fetch_production(logger=test_logger))

    print("fetch_consumption() ->")
    pprint(fetch_consumption(logger=test_logger))
