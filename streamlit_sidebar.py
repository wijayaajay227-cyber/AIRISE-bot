import streamlit as st

MENU_ITEMS = [
    ("Beranda", "home"),
    ("Pasar", "markets"),
    ("Strategi", "strategy"),
    ("Sinyal", "signals"),
    ("Riwayat", "history"),
    ("Pengaturan", "settings"),
]

PROFILE_BUTTONS = [
    ("Akun Saya", "profile"),
    ("Keluar", "logout"),
]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --sidebar-width: 280px;
            --sidebar-bg: #07101a;
            --sidebar-border: rgba(148, 163, 184, 0.16);
            --button-bg: rgba(148, 163, 184, 0.08);
            --button-hover: rgba(14, 165, 233, 0.18);
            --button-active: #38bdf8;
            --text-color: #e2e8f0;
            --shadow: 0 32px 100px rgba(0, 0, 0, 0.18);
        }

        .responsive-shell {
            display: flex;
            min-height: 100vh;
            background: #03060f;
            color: var(--text-color);
            font-family: Inter, ui-sans-serif, system-ui, sans-serif;
        }

        .sidebar-toggle {
            display: none;
        }

        .sidebar-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.46);
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.26s ease, visibility 0.26s ease;
            z-index: 30;
            cursor: pointer;
        }

        .sidebar {
            width: var(--sidebar-width);
            min-width: var(--sidebar-width);
            background: linear-gradient(180deg, #07101a 0%, #0f172a 100%);
            border-right: 1px solid var(--sidebar-border);
            box-shadow: var(--shadow);
            padding: 28px 22px;
            position: fixed;
            left: 0;
            top: 0;
            bottom: 0;
            z-index: 40;
            overflow-y: auto;
            transition: transform 0.26s ease, opacity 0.26s ease;
        }

        .sidebar-close {
            display: none;
            justify-content: flex-end;
            margin-bottom: 18px;
        }

        .sidebar-close label {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 42px;
            height: 42px;
            border-radius: 14px;
            background: rgba(148, 163, 184, 0.08);
            color: var(--text-color);
            border: 1px solid transparent;
            cursor: pointer;
            transition: transform 0.16s ease, background 0.16s ease, border-color 0.16s ease;
        }

        .sidebar-close label:hover,
        .sidebar-close label:focus-visible {
            background: var(--button-hover);
            border-color: rgba(34, 211, 238, 0.26);
            transform: scale(1.04);
            outline: none;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 32px;
        }

        .brand-crest {
            width: 48px;
            height: 48px;
            border-radius: 16px;
            background: radial-gradient(circle at 30% 30%, #22d3ee, #0f172a 88%);
            display: grid;
            place-items: center;
            box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.1);
        }

        .brand-crest span {
            font-size: 1.1rem;
            color: #0f172a;
            font-weight: 800;
        }

        .brand-title {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .brand-title h1 {
            margin: 0;
            font-size: 1.18rem;
            color: #f8fafc;
        }

        .brand-title p {
            margin: 0;
            font-size: 0.86rem;
            color: #a5b4fc;
        }

        .sidebar-links,
        .sidebar-footer {
            display: grid;
            gap: 10px;
        }

        .sidebar-footer {
            margin-top: auto;
            padding-top: 8px;
            border-top: 1px solid rgba(148, 163, 184, 0.08);
        }

        .nav-button,
        .footer-button {
            display: block;
            width: 100%;
            padding: 14px 16px;
            border-radius: 14px;
            background: rgba(148, 163, 184, 0.08);
            color: var(--text-color);
            text-decoration: none;
            transition: background 0.18s ease, transform 0.18s ease, border-color 0.18s ease;
            border: 1px solid transparent;
            font-size: 0.96rem;
            font-weight: 500;
        }

        .nav-button:hover,
        .footer-button:hover,
        .nav-button:focus-visible,
        .footer-button:focus-visible {
            background: var(--button-hover);
            border-color: rgba(34, 211, 238, 0.26);
            transform: translateX(2px);
            outline: none;
        }

        .content {
            flex: 1;
            margin-left: var(--sidebar-width);
            padding: 32px 34px 34px 34px;
            min-height: 100vh;
            box-sizing: border-box;
        }

        .mobile-menu-label {
            display: none;
            position: fixed;
            z-index: 100;
            left: 18px;
            top: 18px;
            width: 52px;
            height: 52px;
            border-radius: 16px;
            background: rgba(14, 165, 233, 0.16);
            border: 1px solid rgba(56, 189, 248, 0.24);
            display: grid;
            place-items: center;
            cursor: pointer;
            transition: transform 0.16s ease, background 0.16s ease;
        }

        .mobile-menu-label:hover {
            transform: scale(1.05);
            background: rgba(14, 165, 233, 0.24);
        }

        .mobile-menu-label span {
            font-size: 1.5rem;
            color: #e0f2fe;
        }

        @media (max-width: 860px) {
            .sidebar {
                width: min(78vw, 320px);
                transform: translateX(-100%);
                opacity: 0;
                visibility: hidden;
            }

            .sidebar-toggle:checked ~ .sidebar {
                transform: translateX(0);
                opacity: 1;
                visibility: visible;
            }

            .sidebar-toggle:checked ~ .sidebar-backdrop {
                opacity: 1;
                visibility: visible;
            }

            .content {
                margin-left: 0;
                padding: 24px 18px 18px 18px;
            }

            .mobile-menu-label {
                display: grid;
            }

            .sidebar-close {
                display: flex;
            }
        }

        @media (max-width: 520px) {
            .nav-button,
            .footer-button {
                padding: 16px 18px;
                font-size: 1rem;
            }

            .sidebar {
                padding: 22px 16px;
            }

            .content {
                padding-top: 80px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    sidebar_html = [
        '<div class="responsive-shell">',
        '  <input type="checkbox" id="sidebar-toggle" class="sidebar-toggle" />',
        '  <label for="sidebar-toggle" class="sidebar-backdrop"></label>',
        '  <label for="sidebar-toggle" class="mobile-menu-label"><span>☰</span></label>',
        '  <aside class="sidebar">',
        '    <div class="sidebar-close"><label for="sidebar-toggle">✕</label></div>',
        '    <div class="brand">',
        '      <div class="brand-crest"><span>A</span></div>',
        '      <div class="brand-title">',
        '        <h1>AIRISE</h1>',
        '        <p>Crypto Futures Analyzer</p>',
        '      </div>',
        '    </div>',
        '    <div class="sidebar-links">',
    ]

    for label, _key in MENU_ITEMS:
        sidebar_html.append(f'      <a href="#" class="nav-button">{label}</a>')

    sidebar_html.extend(
        [
            '    </div>',
            '    <div class="sidebar-footer">',
        ]
    )

    for label, _key in PROFILE_BUTTONS:
        sidebar_html.append(f'      <a href="#" class="footer-button">{label}</a>')

    sidebar_html.extend(
        [
            '    </div>',
            '  </aside>',
            '  <main class="content">',
            '    <h2>Responsive Sidebar Demo</h2>',
            '    <p>Sidebar ini tetap berada di sisi kiri pada desktop dan otomatis beralih ke menu hamburger pada perangkat mobile.</p>',
            '    <p>Semua tombol dibuat touch-friendly, dengan hover effect untuk desktop.</p>',
            '    <div style="margin-top: 28px; color: #cbd5e1;">',
            '      <h3>Petunjuk</h3>',
            '      <ul style="margin-top: 12px; padding-left: 20px;">',
            '        <li>Gunakan tombol ☰ di pojok kiri atas pada layar kecil.</li>',
            '        <li>Sidebar dapat dibuka dan ditutup dengan transisi halus.</li>',
            '        <li>Tombol navigasi memiliki ukuran dan ruang sentuh yang sesuai.</li>',
            '      </ul>',
            '    </div>',
            '  </main>',
            '</div>',
        ]
    )

    st.markdown("\n".join(sidebar_html), unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="AIRISE Responsive Sidebar", layout="wide")
    inject_styles()
    render_sidebar()


if __name__ == "__main__":
    main()
