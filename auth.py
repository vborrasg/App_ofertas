"""
auth.py — Autenticación con Login + OTP (mismo patrón que Forecast).
"""
import streamlit as st
import random
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from data import load_users


def init_session():
    for k, v in [
        ("authenticated", False),
        ("user_email", ""),
        ("user_nombre", ""),
        ("user_rol", ""),
        ("otp_code", ""),
        ("otp_sent", False),
        ("login_step", "credentials"),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v


def _send_otp(email_to, otp):
    try:
        smtp_user = st.secrets["SMTP_USER"]
        smtp_pass = st.secrets["SMTP_PASSWORD"]
        smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(st.secrets.get("SMTP_PORT", "587"))
    except Exception:
        print(f"[DEV] OTP para {email_to}: {otp}", file=sys.stderr)
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = email_to
        msg["Subject"] = "🔐 Código de acceso — App Ofertas Knauf"
        body = f"""
        <html><body style="font-family:Arial;padding:20px;">
        <h2>Tu código de acceso</h2>
        <p style="font-size:32px;font-weight:bold;color:#1a5276;
                  background:#eaf2f8;padding:20px;text-align:center;
                  border-radius:8px;letter-spacing:8px;">{otp}</p>
        <p>Este código caduca en 10 minutos.</p>
        <hr><p style="color:#888;font-size:12px;">App Ofertas — Knauf Industries</p>
        </body></html>
        """
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[ERROR SMTP] {e}", file=sys.stderr)
        return False


def render_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Acceso — Ofertas Knauf")

        if st.session_state.login_step == "credentials":
            with st.form("login_form"):
                email = st.text_input("📧 Email", placeholder="tu@email.com")
                password = st.text_input("🔑 Contraseña", type="password")
                submit = st.form_submit_button("Acceder", use_container_width=True)

                if submit and email and password:
                    users = load_users()
                    email_clean = email.strip().lower()
                    if email_clean in users and users[email_clean]["password"] == password:
                        otp = f"{random.randint(100000, 999999)}"
                        st.session_state.otp_code = otp
                        st.session_state.user_email = email_clean
                        st.session_state.user_nombre = users[email_clean]["nombre"]
                        st.session_state.user_rol = users[email_clean]["rol"]
                        st.session_state.otp_sent = _send_otp(email_clean, otp)
                        st.session_state.login_step = "otp"
                        st.rerun()
                    else:
                        st.error("❌ Email o contraseña incorrectos")

        elif st.session_state.login_step == "otp":
            if st.session_state.otp_sent:
                st.info(f"📬 Código enviado a **{st.session_state.user_email}**")
            else:
                st.warning("⚠️ No se pudo enviar el email. Contacta con el administrador.")

            with st.form("otp_form"):
                code = st.text_input("🔢 Código OTP", type="password",
                                     placeholder="6 dígitos", max_chars=6)
                verify = st.form_submit_button("Verificar", use_container_width=True)
                if verify:
                    if code == st.session_state.otp_code:
                        st.session_state.authenticated = True
                        st.session_state.login_step = "done"
                        st.rerun()
                    else:
                        st.error("❌ Código incorrecto")

            if st.button("← Volver al login"):
                st.session_state.login_step = "credentials"
                st.rerun()
