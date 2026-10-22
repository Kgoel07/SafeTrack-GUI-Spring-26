# ═══════════════════════════════════════════════════════
# i18n.py  –  English / Kiswahili translations
#
# All UI text is written in English and passed through tr().  When the
# language is Kiswahili ("sw"), tr() looks the English text up in SW below.
# Text with values uses placeholders:  tr("Node {n}", n=5)
#
# The language is chosen per user in Settings → App Preferences.  The login
# screen uses the last language picked on this computer.
# ═══════════════════════════════════════════════════════

import re
from datetime import datetime

from PyQt6.QtWidgets import QMessageBox

LANGUAGES = {"en": "English", "sw": "Kiswahili"}

_lang = "en"


def set_language(code: str):
    global _lang
    _lang = code if code in LANGUAGES else "en"


def get_language() -> str:
    return _lang


def tr(text: str, **kwargs) -> str:
    """Translate English UI text into the current language."""
    if _lang == "sw":
        text = SW.get(text, text)
    return text.format(**kwargs) if kwargs else text


# ───────────────────────────────────────────────────────
# Alert text stored in the database (written in English by notification.py)
# ───────────────────────────────────────────────────────
_NOTIF_PATTERNS = [
    (r"New Node (\S+) SOS Alert",            "Tahadhari Mpya ya SOS: Kifaa {0}"),
    (r"Node (\S+) SOS Alert",                "Tahadhari ya SOS: Kifaa {0}"),
    (r"Node (\S+) has been added",           "Kifaa {0} kimeongezwa"),
    (r"Node (\S+) has been removed",         "Kifaa {0} kimeondolewa"),
    (r"Node (\S+) Disconnected",             "Kifaa {0} kimetenganishwa"),
    (r"Node (\S+) Reconnected",              "Kifaa {0} kimeunganishwa tena"),
    (r"Node (\S+) Location Update",          "Mahali papya pa Kifaa {0}"),
    (r"Node (\S+) Status: (.*)",             "Hali ya Kifaa {0}: {1}"),
    (r"Node (\S+) ALERT",                    "TAHADHARI: Kifaa {0}"),
    (r"Current location: (.*)",              "Mahali pa sasa: {0}"),
    (r"Last recorded location: (.*)",        "Mahali palipohifadhiwa mwisho: {0}"),
    (r"Last known location: (.*)",           "Mahali palipojulikana mwisho: {0}"),
    (r"Present location: (.*)",              "Mahali pa sasa: {0}"),
    (r"Location: (.*)",                      "Mahali: {0}"),
]


def notif_text(text: str) -> str:
    """Translate a notification title/message that was stored in English."""
    if _lang != "sw" or not text:
        return text
    if text in SW:
        return SW[text]
    for pattern, sw in _NOTIF_PATTERNS:
        m = re.fullmatch(pattern, text)
        if m:
            groups = [notif_text(g) for g in m.groups()]
            return sw.format(*groups)
    return text.replace("(UNAUTHORIZED)", SW["(UNAUTHORIZED)"])


# ───────────────────────────────────────────────────────
# Dates and times
# ───────────────────────────────────────────────────────
_SW_MONTHS = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ago", "Sep", "Okt", "Nov", "Des"]


def short_datetime(dt: datetime) -> str:
    """e.g. 'Sep 25, 17:25' / '25 Sep, 17:25'."""
    if _lang == "sw":
        return f"{dt.day} {_SW_MONTHS[dt.month - 1]}, {dt:%H:%M}"
    return f"{dt:%b %d, %H:%M}"


def time_ago(secs: int) -> str:
    if secs < 60:
        return tr("just now")
    if secs < 3600:
        return tr("{n} min ago", n=secs // 60)
    if secs < 86400:
        return tr("{n} hr ago", n=secs // 3600)
    days = secs // 86400
    return tr("{n} day ago", n=days) if days == 1 else tr("{n} days ago", n=days)


# ───────────────────────────────────────────────────────
# Message boxes with translated buttons
# ───────────────────────────────────────────────────────
def _box(parent, icon, title, text):
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    return box


def info(parent, title: str, text: str):
    box = _box(parent, QMessageBox.Icon.Information, title, text)
    box.addButton(tr("OK"), QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def warn(parent, title: str, text: str):
    box = _box(parent, QMessageBox.Icon.Warning, title, text)
    box.addButton(tr("OK"), QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def confirm(parent, title: str, text: str, yes: str = "Yes", no: str = "No",
            warning: bool = False) -> bool:
    box = _box(parent, QMessageBox.Icon.Warning if warning else QMessageBox.Icon.Question, title, text)
    yes_btn = box.addButton(tr(yes), QMessageBox.ButtonRole.YesRole)
    no_btn = box.addButton(tr(no), QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no_btn)
    box.exec()
    return box.clickedButton() is yes_btn


# ───────────────────────────────────────────────────────
# Kiswahili dictionary  (English source text -> Kiswahili)
# ───────────────────────────────────────────────────────
SW = {
    # ── General ──
    "OK": "Sawa",
    "Yes": "Ndiyo",
    "No": "Hapana",
    "Cancel": "Ghairi",
    "Refresh": "Onyesha upya",
    "My Nodes": "Vifaa Vyangu",
    "Admin": "Msimamizi",
    "User": "Mtumiaji",
    "Coming soon": "Inakuja hivi karibuni",
    "View on Map": "Tazama kwenye Ramani",
    "Dismiss": "Funga",
    "Login": "Ingia",
    "just now": "sasa hivi",
    "{n} min ago": "dakika {n} zilizopita",
    "{n} hr ago": "saa {n} zilizopita",
    "{n} day ago": "siku {n} iliyopita",
    "{n} days ago": "siku {n} zilizopita",
    "Updated {time}": "Imesasishwa {time}",

    # ── Sidebar / main window ──
    "NAVIGATION": "URAMBAZAJI",
    "Map": "Ramani",
    "Nodes": "Vifaa",
    "Notifications": "Arifa",
    "History && Logs": "Historia",   # sidebar label – kept short to fit
    "History & Logs": "Historia na Kumbukumbu",
    "History & Log": "Historia na Kumbukumbu",
    "Settings": "Mipangilio",
    "Invite": "Alika",
    "Logout": "Toka",
    "Log out": "Toka",
    "Are you sure you want to log out?": "Una uhakika unataka kutoka?",
    "Permission Denied": "Ruhusa Imekataliwa",
    "Only admins can create invite codes.": "Ni wasimamizi pekee wanaoweza kuunda misimbo ya mwaliko.",
    "Invite Code Generated": "Msimbo wa Mwaliko Umeundwa",
    "Share this code with the person you want to invite:\n\n    {code}\n\n"
    "It expires in 48 hours and can only be used once.":
        "Mpe mtu unayetaka kumwalika msimbo huu:\n\n    {code}\n\n"
        "Unaisha baada ya saa 48 na unaweza kutumika mara moja tu.",

    # ── Notification / history filters & cards ──
    "All": "Zote",
    "SOS": "SOS",
    "Alert": "Tahadhari",
    "Info": "Taarifa",
    "System": "Mfumo",
    "No new notifications": "Hakuna arifa mpya",
    "(UNAUTHORIZED TO VIEW LOCATION)": "(HUNA RUHUSA YA KUONA MAHALI)",
    "(UNAUTHORIZED)": "(HAKUNA RUHUSA)",
    "Node Alert": "Tahadhari ya Kifaa",
    "Node {n}: {gps}": "Kifaa {n}: {gps}",

    # ── Nodes page ──
    "Active": "Amilifu",
    "Inactive": "Si Amilifu",
    "Unknown": "Haijulikani",
    "NODE": "KIFAA",
    "LAST SEEN": "ILIONEKANA MWISHO",
    "LOCATION": "MAHALI",
    "Hidden": "Imefichwa",
    "Latitude, longitude": "Latitudo, longitudo",
    "You don't have access to this node": "Huna ruhusa ya kuona kifaa hiki",
    "No nodes in the database yet": "Bado hakuna vifaa kwenye hifadhidata",
    "No nodes match this filter": "Hakuna vifaa vinavyolingana na kichujio hiki",

    # ── Settings page ──
    "Back": "Rudi",
    "Save Changes": "Hifadhi Mabadiliko",
    "Account": "Akaunti",
    "Privacy & Security": "Faragha na Usalama",
    "App Preferences": "Mapendeleo",
    "Emergency Contacts": "Anwani za Dharura",
    "About & Help": "Kuhusu na Msaada",
    "Saved": "Imehifadhiwa",
    "Your settings have been saved.": "Mipangilio yako imehifadhiwa.",
    "Couldn't Save": "Imeshindwa Kuhifadhi",

    # Account
    "Account Settings": "Mipangilio ya Akaunti",
    "Your profile details. Click Save Changes to update them.":
        "Taarifa zako binafsi. Bofya Hifadhi Mabadiliko ili kuzisasisha.",
    "Enter your full name": "Weka jina lako kamili",
    "Enter email address": "Weka anwani ya barua pepe",
    "Enter phone number (optional)": "Weka namba ya simu (si lazima)",
    "Full Name": "Jina Kamili",
    "Username": "Jina la Mtumiaji",
    "Email": "Barua Pepe",
    "Phone Number": "Namba ya Simu",
    "Usernames can't be changed.": "Jina la mtumiaji haliwezi kubadilishwa.",
    "Used to recover your account if you forget your password.":
        "Hutumika kurejesha akaunti yako ukisahau nenosiri.",
    "That email is already used by another account.": "Barua pepe hiyo tayari inatumiwa na akaunti nyingine.",
    "Enter a valid phone number (digits, spaces, +, - and brackets only).":
        "Weka namba sahihi ya simu (tarakimu, nafasi, +, - na mabano pekee).",
    "Could not update your profile.": "Imeshindwa kusasisha wasifu wako.",

    # Privacy & Security
    "Manage your password and who can see node locations.":
        "Simamia nenosiri lako na nani anaweza kuona mahali vifaa vilipo.",
    "YOUR ACCESS": "RUHUSA ZAKO",
    "Role": "Wadhifa",
    "Admins can see every node's location and invite other admins.":
        "Wasimamizi wanaweza kuona mahali kila kifaa kilipo na kualika wasimamizi wengine.",
    "Node locations you can view": "Mahali pa vifaa unavyoweza kuona",
    "Locations of other nodes are hidden from you.": "Mahali pa vifaa vingine pamefichwa kwako.",
    "All nodes": "Vifaa vyote",
    "{n} node": "kifaa {n}",
    "{n} nodes": "vifaa {n}",
    "PASSWORD": "NENOSIRI",
    "Current password": "Nenosiri la sasa",
    "New password": "Nenosiri jipya",
    "Confirm new password": "Thibitisha nenosiri jipya",
    "8–12 characters. Must not contain your username or the app name, and can't be a common password.":
        "Herufi 8–12. Lisiwe na jina lako la mtumiaji wala jina la programu, na lisiwe nenosiri la kawaida.",
    "Update Password": "Sasisha Nenosiri",
    "Fill in your current and new password.": "Jaza nenosiri lako la sasa na jipya.",
    "Your current password is incorrect.": "Nenosiri lako la sasa si sahihi.",
    "New passwords do not match.": "Manenosiri mapya hayalingani.",
    "New password must be different from your current one.":
        "Nenosiri jipya lazima liwe tofauti na la sasa.",
    "Could not update your password.": "Imeshindwa kusasisha nenosiri lako.",
    "Password updated.": "Nenosiri limesasishwa.",
    "ADMIN INVITE CODES": "MISIMBO YA MWALIKO WA MSIMAMIZI",
    "Generate Code": "Unda Msimbo",
    "Invite another admin": "Alika msimamizi mwingine",
    "Codes can be used once and expire after 48 hours.":
        "Misimbo inaweza kutumika mara moja na huisha baada ya saa 48.",
    "Invite code: {code}\n\nIt has been copied to your clipboard.":
        "Msimbo wa mwaliko: {code}\n\nUmenakiliwa kwenye ubao wako wa kunakili.",
    "Used by {user}": "Umetumiwa na {user}",
    "Expired": "Umeisha muda",
    "Active · expires {when}": "Unatumika · unaisha {when}",
    "DANGER ZONE": "ENEO HATARI",
    "Delete Account": "Futa Akaunti",
    "Delete account": "Futa akaunti",
    "Permanently removes your account and emergency contacts. This can't be undone.":
        "Inafuta kabisa akaunti yako na anwani za dharura. Hatua hii haiwezi kutenguliwa.",
    "Are you sure you want to delete your account?\nThis action cannot be undone.":
        "Una uhakika unataka kufuta akaunti yako?\nHatua hii haiwezi kutenguliwa.",
    "Confirm Password": "Thibitisha Nenosiri",
    "Enter your password to delete your account:": "Weka nenosiri lako ili kufuta akaunti yako:",
    "Incorrect Password": "Nenosiri Si Sahihi",
    "That password is incorrect.": "Nenosiri hilo si sahihi.",
    "Account Deleted": "Akaunti Imefutwa",
    "Your account has been deleted.": "Akaunti yako imefutwa.",
    "Error": "Hitilafu",
    "Could not delete your account.": "Imeshindwa kufuta akaunti yako.",

    # App Preferences
    "Click Save Changes to apply.": "Bofya Hifadhi Mabadiliko ili kutumia.",
    "APPEARANCE": "MWONEKANO",
    "Light mode": "Hali ya mwanga",
    "Use a light colour scheme. Applies instantly.": "Tumia rangi nyepesi. Inatumika papo hapo.",
    "Language": "Lugha",
    "Language used throughout the app.": "Lugha inayotumika katika programu nzima.",
    "GENERAL": "JUMLA",
    "Start-up page": "Ukurasa wa kuanzia",
    "Page shown after you log in.": "Ukurasa unaoonyeshwa baada ya kuingia.",
    "Time format": "Mfumo wa saa",
    "How timestamps appear on the Nodes page.": "Jinsi muda unavyoonyeshwa kwenye ukurasa wa Vifaa.",
    "24-hour (14:30)": "Saa 24 (14:30)",
    "12-hour (2:30 PM)": "Saa 12 (2:30 PM)",
    "Confirm before logout": "Thibitisha kabla ya kutoka",
    "Ask for confirmation when logging out.": "Uliza uthibitisho unapotoka.",
    "MAP": "RAMANI",
    "Default zoom level": "Kiwango cha kukuza",
    "Zoom used when the map loads or refreshes.": "Ukuzaji unaotumika ramani inapofunguka au kuonyeshwa upya.",
    "City (12)": "Jiji (12)",
    "District (13)": "Wilaya (13)",
    "Neighborhood (14)": "Mtaa (14)",
    "Street (15)": "Barabara (15)",
    "Building (16)": "Jengo (16)",
    "Highlight SOS area": "Angazia eneo la SOS",
    "Draw a red radius around nodes in SOS.": "Chora duara jekundu kuzunguka vifaa vilivyo kwenye SOS.",
    "DATA": "DATA",
    "Keep node history for": "Hifadhi historia ya vifaa kwa",
    "Older location and alert data is removed. Applies the next time you log in.":
        "Data ya zamani ya mahali na tahadhari inafutwa. Inatumika utakapoingia tena.",
    "24 hours": "Saa 24",
    "48 hours": "Saa 48",
    "72 hours": "Saa 72",
    "7 days": "Siku 7",
    "Restore Defaults": "Rejesha Chaguo-msingi",

    # Emergency Contacts
    "People to reach if you're in an emergency. Saved (encrypted) as soon as you add them.":
        "Watu wa kuwasiliana nao ukiwa kwenye dharura. Wanahifadhiwa (kwa usimbaji fiche) mara unapowaongeza.",
    "YOUR CONTACTS": "ANWANI ZAKO",
    "ADD A CONTACT": "ONGEZA ANWANI",
    "Full name": "Jina kamili",
    "Phone number": "Namba ya simu",
    "Name": "Jina",
    "Phone": "Simu",
    "Relationship": "Uhusiano",
    "Parent": "Mzazi",
    "Spouse / Partner": "Mwenzi",
    "Sibling": "Ndugu",
    "Friend": "Rafiki",
    "Roommate": "Mwenzako wa chumba",
    "Other": "Mwingine",
    "Add Contact": "Ongeza Anwani",
    "Limit of {n} reached": "Kikomo cha {n} kimefikiwa",
    "No emergency contacts yet.": "Bado hakuna anwani za dharura.",
    "Remove": "Ondoa",
    "Remove Contact": "Ondoa Anwani",
    "Remove {name} from your emergency contacts?": "Ungependa kumwondoa {name} kwenye anwani zako za dharura?",
    "Enter a valid phone number.": "Weka namba sahihi ya simu.",

    # About & Help
    "ABOUT": "KUHUSU",
    "Spring 2026": "Machipuko 2026",
    "Tracks the location and status of SafeTrack nodes and alerts you the moment a node sends an SOS.":
        "Hufuatilia mahali na hali ya vifaa vya SafeTrack na kukujulisha mara kifaa kinapotuma SOS.",
    "Signed in as": "Umeingia kama",
    "NODE STATUS": "HALI YA KIFAA",
    "The node has sent an emergency alert. Shown in red on the map.":
        "Kifaa kimetuma tahadhari ya dharura. Kinaonyeshwa kwa rangi nyekundu kwenye ramani.",
    "The node is on and reporting its location normally.":
        "Kifaa kimewashwa na kinatuma mahali kilipo kama kawaida.",
    "The node has stopped reporting.": "Kifaa kimeacha kutuma taarifa.",
    "QUICK GUIDE": "MWONGOZO WA HARAKA",
    "Live positions of the nodes you can view. Click Refresh to redraw.":
        "Mahali halisi pa vifaa unavyoweza kuona. Bofya Onyesha upya ili kuchora upya.",
    "Every node in the database with its latest status. Use View on Map to jump to one.":
        "Kila kifaa kwenye hifadhidata pamoja na hali yake ya karibuni. Tumia Tazama kwenye Ramani kukifikia.",
    "New alerts since you last looked. The sidebar badge shows how many are unread.":
        "Tahadhari mpya tangu ulipoangalia mwisho. Alama ya pembeni inaonyesha ngapi hazijasomwa.",
    "Every alert that has been recorded, filterable by type.":
        "Kila tahadhari iliyorekodiwa, inaweza kuchujwa kwa aina.",
    "TROUBLESHOOTING": "UTATUZI WA MATATIZO",
    "Locations say “Unauthorized”": "Mahali panaonyesha “Hakuna ruhusa”",
    "Only admins can see every node. Ask an admin for an invite code, then use "
    "“Have an admin invite code?” on the login screen.":
        "Ni wasimamizi pekee wanaoweza kuona kila kifaa. Omba msimamizi msimbo wa mwaliko, kisha tumia "
        "“Una msimbo wa mwaliko wa msimamizi?” kwenye skrini ya kuingia.",
    "No nodes are showing up": "Hakuna vifaa vinavyoonekana",
    "Check that the SafeTrack receiver is plugged into this computer.":
        "Hakikisha kipokeaji cha SafeTrack kimechomekwa kwenye kompyuta hii.",
    "The map is blank": "Ramani haionyeshi kitu",
    "Offline map tiles are loaded from the tiles folder next to the app. "
    "Run download_map.py to download them again.":
        "Vipande vya ramani vinapakiwa kutoka folda ya tiles iliyo karibu na programu. "
        "Endesha download_map.py ili kuvipakua tena.",
    "Forgot your password": "Umesahau nenosiri lako",
    "Log out and use “forgot password?” on the login screen.":
        "Toka kisha tumia “umesahau nenosiri?” kwenye skrini ya kuingia.",
    "SYSTEM": "MFUMO",
    "Database": "Hifadhidata",
    "Nodes stored": "Vifaa vilivyohifadhiwa",
    "Alerts stored": "Tahadhari zilizohifadhiwa",

    # ── Login screens ──
    "SafeTrack – Login": "SafeTrack – Ingia",
    "LOG IN": "INGIA",
    "username": "jina la mtumiaji",
    "password": "nenosiri",
    "forgot password?": "umesahau nenosiri?",
    "Log In": "Ingia",
    "Don't have an account?": "Huna akaunti?",
    "Sign up!": "Jisajili!",
    "Have an admin invite code?": "Una msimbo wa mwaliko wa msimamizi?",
    "Please enter a username.": "Tafadhali weka jina la mtumiaji.",
    "Please enter your password.": "Tafadhali weka nenosiri lako.",
    "Invalid username or password.": "Jina la mtumiaji au nenosiri si sahihi.",
    "CREATE ACCOUNT": "FUNGUA AKAUNTI",
    "full name": "jina kamili",
    "password (8–12 chars)": "nenosiri (herufi 8–12)",
    "confirm password": "thibitisha nenosiri",
    "Sign Up": "Jisajili",
    "Already have an account?": "Tayari una akaunti?",
    "Log in!": "Ingia!",
    "✓": "✓",
    "That username is already taken.": "Jina hilo la mtumiaji tayari limechukuliwa.",
    "✓ Username available": "✓ Jina la mtumiaji linapatikana",
    "✓ Strong password": "✓ Nenosiri imara",
    "✓ Passwords match": "✓ Manenosiri yanalingana",
    "Passwords do not match.": "Manenosiri hayalingani.",
    "Could not create account. Try again.": "Imeshindwa kufungua akaunti. Jaribu tena.",
    "Account created! You can now log in.": "Akaunti imefunguliwa! Sasa unaweza kuingia.",
    "FORGOT PASSWORD": "UMESAHAU NENOSIRI",
    "Enter the email linked to your account.\nWe'll send a reset code.":
        "Weka barua pepe iliyounganishwa na akaunti yako.\nTutakutumia msimbo wa kubadilisha nenosiri.",
    "email": "barua pepe",
    "Send Reset Code": "Tuma Msimbo",
    "Already have a code?": "Tayari una msimbo?",
    "Enter code": "Weka msimbo",
    "← Back to login": "← Rudi kwenye kuingia",
    "If that email is registered, a reset code has been sent.":
        "Ikiwa barua pepe hiyo imesajiliwa, msimbo wa kubadilisha nenosiri umetumwa.",
    "Reset code sent! Check your inbox.": "Msimbo umetumwa! Angalia kikasha chako.",
    "Reset code (SMTP not configured):\n{token}\n\nCopy this code and click 'Enter code' below.":
        "Msimbo wa kubadilisha nenosiri (barua pepe haijawekwa):\n{token}\n\n"
        "Nakili msimbo huu kisha bofya 'Weka msimbo' hapa chini.",
    "RESET PASSWORD": "BADILISHA NENOSIRI",
    "paste your reset code": "bandika msimbo wako",
    "new password (8–12 chars)": "nenosiri jipya (herufi 8–12)",
    "confirm new password": "thibitisha nenosiri jipya",
    "Reset Password": "Badilisha Nenosiri",
    "Paste the reset code you received.": "Bandika msimbo uliopokea.",
    "Invalid or expired reset code.": "Msimbo si sahihi au muda wake umeisha.",
    "Password updated! You can now log in.": "Nenosiri limesasishwa! Sasa unaweza kuingia.",
    "ADMIN INVITE": "MWALIKO WA MSIMAMIZI",
    "An existing admin has sent you an invite code.\nEnter it below along with your account credentials.":
        "Msimamizi amekutumia msimbo wa mwaliko.\nUweke hapa chini pamoja na taarifa za akaunti yako.",
    "invite code": "msimbo wa mwaliko",
    "your username": "jina lako la mtumiaji",
    "your password": "nenosiri lako",
    "Activate Admin Access": "Washa Ruhusa ya Msimamizi",
    "No account yet?": "Bado huna akaunti?",
    "Sign up first": "Jisajili kwanza",
    "All fields are required.": "Sehemu zote zinahitajika.",
    "Invalid or expired invite code.": "Msimbo wa mwaliko si sahihi au muda wake umeisha.",
    "Success! '{username}' now has admin access.\nGo back to login to continue.":
        "Imefanikiwa! '{username}' sasa ana ruhusa ya msimamizi.\nRudi kwenye kuingia ili kuendelea.",

    # ── Validation messages (auth_utils.py) ──
    "Username is required.": "Jina la mtumiaji linahitajika.",
    "Username must be 3–18 characters (letters, digits, . _ - only).":
        "Jina la mtumiaji liwe na herufi 3–18 (herufi, tarakimu, . _ - pekee).",
    "That username is reserved.": "Jina hilo la mtumiaji limehifadhiwa.",
    "Password must be at least 8 characters.": "Nenosiri liwe na angalau herufi 8.",
    "Password must be 12 characters or fewer.": "Nenosiri lisizidi herufi 12.",
    "That password is too common. Choose something unique.":
        "Nenosiri hilo ni la kawaida mno. Chagua jingine la kipekee.",
    "Password must not contain your username.": "Nenosiri lisiwe na jina lako la mtumiaji.",
    "Password must not contain the app name.": "Nenosiri lisiwe na jina la programu.",
    "Password is too simple – use more variety.": "Nenosiri ni rahisi mno – tumia mchanganyiko zaidi.",
    "Email is required.": "Barua pepe inahitajika.",
    "Enter a valid email address.": "Weka anwani sahihi ya barua pepe.",
    "Full name must be at least 2 characters.": "Jina kamili liwe na angalau herufi 2.",
    "Full name is too long.": "Jina kamili ni refu mno.",
    "Full name can only contain letters, spaces, hyphens, and apostrophes.":
        "Jina kamili linaweza kuwa na herufi, nafasi, vistari na aposta pekee.",
    "Name must be at least 2 characters.": "Jina liwe na angalau herufi 2.",
    "Name is too long.": "Jina ni refu mno.",
    "Name can only contain letters, spaces, hyphens, and apostrophes.":
        "Jina linaweza kuwa na herufi, nafasi, vistari na aposta pekee.",
}
