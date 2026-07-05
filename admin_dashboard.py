import requests
import streamlit as st

from config import API_URL
from logger import logger



def render():
    logout_col1, logout_col2 = st.columns([9,1])

    with logout_col2:

        if st.button("Logout"):

            st.session_state.logged_in = False
            st.session_state.role = None

            st.rerun()
    # =====================================================
    # API HELPERS
    # =====================================================

    def api_get(endpoint):

        try:

            logger.info(f"GET {endpoint}")

            response = requests.get(
                f"{API_URL}{endpoint}",
                timeout=30
            )

            response.raise_for_status()


            return response.json()

        except Exception:

            logger.exception(
                f"GET Failed : {endpoint}"
            )

            raise


    def api_post(endpoint):

        try:

            logger.info(f"POST {endpoint}")

            response = requests.post(
                f"{API_URL}{endpoint}",
                timeout=120
            )

            response.raise_for_status()


            return response.json()

        except Exception:

            logger.exception(
                f"POST Failed : {endpoint}"
            )

            raise


    # =====================================================
    # STYLING
    # =====================================================
    st.markdown("""
    <style>

    /* PAGE */
    .stApp{
        background:#f5f8fc;
    }

    /* MAIN CONTAINER */
    .main .block-container{
        max-width:1400px;
        padding-top:2rem;
    }

    /* SECTION HEADER */
    .section-header{
        background:#eef5ff;
        border-radius:10px;
        padding:18px;
        margin-bottom:20px;
        border-left:5px solid #1d4ed8;
    }

    .section-header h3{
        color:#173b6c;
        margin:0;
    }

    .section-header p{
        color:#6b7280;
        margin-top:6px;
    }

    /* METRIC CARDS */
    [data-testid="stMetric"]{
        background:white;
        border:1px solid #dbe4f0;
        border-radius:12px;
        padding:20px;
        box-shadow:0 1px 2px rgba(0,0,0,0.04);
    }

    [data-testid="stMetricLabel"]{
        color:#64748b;
        font-weight:600;
    }

    [data-testid="stMetricValue"]{
        color:#0f172a;
        font-weight:700;
    }

    /* BUTTONS */
    .stButton > button{
        background:#2563eb;
        color:white;
        border:none;
        border-radius:8px;
        font-weight:600;
        height:46px;
    }

    .stButton > button:hover{
        background:#1d4ed8;
        color:white;
    }

    /* INFO BOX */
    [data-testid="stInfo"]{
        background:#eef5ff;
        border:1px solid #c7ddff;
    }

    /* TITLE */
    .admin-title{
        text-align:center;
        color:#173b6c;
        font-size:42px;
        font-weight:700;
        margin-bottom:0;
    }

    .admin-subtitle{
        text-align:center;
        color:#6b7280;
        margin-top:5px;
        margin-bottom:25px;
    }

    </style>
    """, unsafe_allow_html=True)

    # =====================================================
    # HEADER
    # =====================================================

    st.markdown("""
    <div class="admin-title">
    Admin Dashboard
    </div>

    <div class="admin-subtitle">
    Signed in as Admin 
    </div>
    """, unsafe_allow_html=True)
   
    # =====================================================
    # LOAD STATS
    # =====================================================

    try:

        logger.info(
            "Loading admin statistics..."
        )

        stats = api_get(
            "/admin/stats"
        )

    except Exception:

        logger.exception(
            "Unable to load admin dashboard"
        )

        st.error(
            "Unable to connect to backend."
        )

        st.stop()

    # =====================================================
    # OVERVIEW PANEL
    # =====================================================

    st.markdown("""
    <div class="section-header">
    <h3>Ticket Overview</h3>
    <p>Current operational state from MySQL</p>
    </div>
    """, unsafe_allow_html=True)

    c1,c2,c3,c4,c5,c6 = st.columns(6)

    with c1:
        st.metric(
            "Total Tickets",
            stats["total"]
        )

    with c2:
        st.metric(
            "Open",
            stats["open"]
        )

    with c3:
        st.metric(
            "In Progress",
            stats["inprogress"]
        )

    with c4:
        st.metric(
            "Resolved",
            stats["resolved"]
        )

    with c5:
        st.metric(
            "Not Ingested",
            stats["not_ingested"]
        )

    with c6:
        st.metric(
            "Vectorized",
            stats["vectorized"]
        )

    # =====================================================
    # ACTION BUTTONS
    # =====================================================

    st.markdown("""
    <div class="section-header">
    </div>
    """, unsafe_allow_html=True)

    left_space, refresh_col, ingest_col, right_space = st.columns(
        [3, 1.2, 1.4, 3]
    )

    with refresh_col:

        if st.button(
            " Refresh Dashboard",
            use_container_width=True
        ):
            st.rerun()

    with ingest_col:

        if st.button(
        "Trigger Knowledge Ingestion",
        type="primary"
        ):

            logger.info(
                "Knowledge ingestion requested by Admin"
            )

            try:

                with st.spinner(
                    "Running ingestion pipeline..."
                ):

                    result = api_post(
                        "/admin/trigger-ingestion"
                    )

                if result["status"] == "success":

                    logger.info(
                        "Knowledge ingestion completed."
                    )

                    st.success(
                        result["message"]
                    )

                    st.rerun()

                else:

                    logger.error(
                        result["message"]
                    )

                    st.error(
                        result["message"]
                    )

            except Exception:

                logger.exception(
                    "Knowledge ingestion failed"
                )

                st.error(
                    "Unable to trigger ingestion."
                )

    st.write("")
    st.write("")

    