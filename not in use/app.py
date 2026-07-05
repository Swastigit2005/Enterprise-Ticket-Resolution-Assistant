import streamlit as st

st.set_page_config(
    page_title="AutoKBase",
    page_icon="🧠",
    layout="wide"
)

# -------------------------
# SESSION
# -------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None


# -------------------------
# LOGIN SCREEN
# -------------------------

if not st.session_state.logged_in:

    st.markdown("""
<style>

.stApp{
    background:#f4f8fd;
}

/* hide default anchor */
#MainMenu{
    visibility:hidden;
}

/* Login Card */
.login-card{
    max-width:540px;
    margin:70px auto 30px auto;
    background:white;
    border-radius:18px;
    padding:45px;
    text-align:center;
    box-shadow:0 10px 30px rgba(0,0,0,.08);
}

.login-logo{
    width:70px;
    height:70px;
    background:#2563eb;
    color:white;
    border-radius:16px;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:28px;
    font-weight:bold;
    margin:auto;
    margin-bottom:20px;
}

.login-title{
    color:#173b6c;
    font-size:42px;
    font-weight:700;
    margin-bottom:10px;
}

.login-sub{
    color:#64748b;
    font-size:18px;
    margin-bottom:25px;
}

div[data-testid="stTextInput"] label{
    color:#173b6c !important;
    font-weight:600 !important;
}

.stTextInput input{
    background:white !important;
    color:#0f172a !important;
    border:1px solid #dbe4f0 !important;
    border-radius:10px !important;
}

.stButton button{
    background:#2563eb !important;
    color:white !important;
    height:46px;
    border:none;
    border-radius:8px;
    font-weight:600;
}

.stButton button:hover{
    background:#1d4ed8 !important;
}

</style>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="login-card">

<div class="login-logo">
AK
</div>

<div class="login-title">
AutoKBase
</div>

<div class="login-sub">
AI-powered knowledge reuse for managed services operations
</div>

</div>
""", unsafe_allow_html=True)

    username = st.text_input("Username")

    password = st.text_input(
        "Password",
        type="password"
    )

    c1,c2 = st.columns(2)

    with c1:

        if st.button(
            "Sign in as Admin",
            use_container_width=True
        ):

            if (
                username=="admin"
                and
                password=="admin123"
            ):

                st.session_state.logged_in=True
                st.session_state.role="admin"

                st.rerun()

            else:

                st.error("Invalid Admin credentials.")

    with c2:

        if st.button(
            "Sign in as Advocate",
            use_container_width=True
        ):

            if (
                username=="advocate"
                and
                password=="advocate123"
            ):

                st.session_state.logged_in=True
                st.session_state.role="advocate"

                st.rerun()

            else:

                st.error("Invalid Advocate credentials.")

    st.stop()


# -------------------------
# DASHBOARD ROUTING
# -------------------------

if st.session_state.role=="admin":

    import admin_dashboard

else:

    import advocate_dashboard