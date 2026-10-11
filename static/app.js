// ======== THEME & LANG MANAGER ========
const translations = {
    fa: {
        dashboard: "داشبورد",
        users: "کاربران",
        add_user: "ساخت کاربر",
        logout: "خروج",
        total_users: "کل کاربران",
        active_users: "کاربر فعال",
        disabled_users: "غیرفعال",
        total_traffic: "ترافیک کل",
        server_online: "هسته Xray فعال است",
        server_offline: "هسته Xray خاموش است",
        new_user: "ساخت کاربر جدید",
        no_users: "هنوز کاربری ساخته نشده",
        username: "نام کاربری",
        password: "رمز عبور",
        login_btn: "ورود به پنل",
        panel_mgmt: "مدیریت پنل",
        welcome: "خوش آمدید",
        settings: "تنظیمات",
        telegram: "بات تلگرام",
        traffic: "مصرف ترافیک",
        creator_support: "پشتیبانی سازنده",
    },
    en: {
        dashboard: "Dashboard",
        users: "Users",
        add_user: "Add User",
        logout: "Logout",
        total_users: "Total Users",
        active_users: "Active Users",
        disabled_users: "Disabled",
        total_traffic: "Total Traffic",
        server_online: "Xray Core is Running",
        server_offline: "Xray Core is Stopped",
        new_user: "Create New User",
        no_users: "No users created yet",
        username: "Username",
        password: "Password",
        login_btn: "Login to Panel",
        panel_mgmt: "Panel Management",
        welcome: "Welcome",
        settings: "Settings",
        telegram: "Telegram Bot",
        traffic: "Traffic Monitor",
        creator_support: "Creator Support",
    }
};

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.innerHTML = theme === 'dark' 
            ? '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
            : '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
    }
}

function applyLang(lang) {
    document.body.setAttribute('data-lang', lang);
    document.documentElement.setAttribute('lang', lang);
    localStorage.setItem('lang', lang);
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang] && translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });
}

function toggleTheme() {
    const cur = localStorage.getItem('theme') || 'dark';
    applyTheme(cur === 'dark' ? 'light' : 'dark');
}

function toggleLang() {
    const cur = localStorage.getItem('lang') || 'fa';
    applyLang(cur === 'fa' ? 'en' : 'fa');
}

function toggleMenu() {
    const menu = document.querySelector('.nav-menu');
    const overlay = document.querySelector('.overlay');
    menu?.classList.toggle('active');
    overlay?.classList.toggle('active');
    
    if (menu?.classList.contains('active')) {
        document.body.style.overflow = 'hidden';
    } else {
        document.body.style.overflow = '';
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const menu = document.querySelector('.nav-menu');
        if (menu?.classList.contains('active')) {
            toggleMenu();
        }
    }
});

document.addEventListener('DOMContentLoaded', () => {
    applyTheme(localStorage.getItem('theme') || 'dark');
    applyLang(localStorage.getItem('lang') || 'fa');
});
