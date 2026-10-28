"""
Στοίχημα – τα πιο πιθανά σημεία ποδοσφαίρου και μπάσκετ, χωρίς εγγραφή.
"""
import datetime
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import NoTransition, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

import betting as B
import model as M

Window.clearcolor = (0.955, 0.96, 0.955, 1)
GREEN, GREY, BLUE, RED = "#0F7B4F", "#6B7486", "#2563C9", "#B4461B"

KV = """
#:import dp kivy.metrics.dp

<Card>:
    size_hint_y: None
    markup: True
    color: 0.11, 0.14, 0.2, 1
    halign: 'left'
    valign: 'top'
    text_size: self.width - dp(36), None
    height: self.texture_size[1] + dp(22)
    padding: dp(18), dp(11)
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.x + dp(8), self.y + dp(3)
            size: self.width - dp(16), self.height - dp(6)
            radius: [dp(10)]

<Plain>:
    size_hint_y: None
    markup: True
    color: 0.11, 0.14, 0.2, 1
    halign: 'left'
    valign: 'top'
    text_size: self.width - dp(28), None
    height: self.texture_size[1] + dp(14)
    padding: dp(14), dp(7)

<Nav@ToggleButton>:
    group: 'nav'
    allow_no_selection: False
    font_size: '12sp'
    background_normal: ''
    background_down: ''
    background_color: (0.95, 0.71, 0.14, 1) if self.state == 'down' else (0.11, 0.14, 0.2, 1)
    color: (0.11, 0.14, 0.2, 1) if self.state == 'down' else (1, 1, 1, 1)

<Root>:
    orientation: 'vertical'
    BoxLayout:
        size_hint_y: None
        height: dp(58)
        padding: dp(12), dp(8)
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: 0.11, 0.14, 0.2, 1
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: 'Στοίχημα · πιθανότητες'
            bold: True
            font_size: '18sp'
            halign: 'left'
            valign: 'middle'
            text_size: self.size
        Button:
            id: upd
            text: 'ΕΝΗΜΕΡΩΣΗ'
            bold: True
            size_hint_x: None
            width: dp(130)
            background_normal: ''
            background_color: 0.95, 0.71, 0.14, 1
            color: 0.11, 0.14, 0.2, 1
            on_release: app.update()
    Label:
        id: msg
        size_hint_y: None
        height: dp(30)
        font_size: '12sp'
        color: 0.42, 0.45, 0.52, 1
        text_size: self.width - dp(20), None
        halign: 'left'
        shorten: True
    ScreenManager:
        id: sm
    BoxLayout:
        size_hint_y: None
        height: dp(56)
        Nav:
            text: 'Σταντάρ'
            state: 'down'
            on_release: app.show('std')
        Nav:
            text: 'Δελτίο'
            on_release: app.show('slip')
        Nav:
            text: 'Αξία'
            on_release: app.show('value')
        Nav:
            text: 'Ιστορικό'
            on_release: app.show('history')
        Nav:
            text: 'Ρυθμίσεις'
            on_release: app.show('settings')
"""


class Card(Label):
    pass


class Plain(Label):
    pass


class Root(BoxLayout):
    pass


Builder.load_string(KV)

FOOT = (f"\n[size=12sp][color={GREY}]Δεν υπάρχει σίγουρο αποτέλεσμα: ένα σημείο με πιθανότητα 80% χάνει 1 στις 5 "
        "φορές. Οι πιθανότητες βγαίνουν από τις αποδόσεις της αγοράς χωρίς το περιθώριο των εταιρειών. Αν η απόδοση "
        "του ΟΠΑΠ/πρακτορείου είναι μικρότερη από τη «δίκαιη», μακροπρόθεσμα χάνεις. Παίζε μόνο ποσά που αντέχεις "
        "να χάσεις.[/color][/size]")


def esc(t):
    return str(t).replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def pct(x):
    return f"{x * 100:.0f}%"


def num(x):
    return f"{x:.2f}".replace(".", ",")


def column():
    sv = ScrollView(do_scroll_x=False)
    col = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2), padding=(0, dp(6)))
    col.bind(minimum_height=col.setter("height"))
    sv.add_widget(col)
    return sv, col


STATUS_TXT = {"εκκρεμεί": "ΕΚΚΡΕΜΕΙ", "κέρδισε": "ΚΕΡΔΙΣΕ", "χάθηκε": "ΧΑΘΗΚΕ"}
REL_COLOR = {"Υψηλή": GREEN, "Μέτρια": BLUE, "Χαμηλή": RED}


def pick_card(m, p, show_best=False, extra=None):
    sport = "Ποδόσφαιρο" if m["sport"] == "football" else "Μπάσκετ"
    color = GREEN if p["prob"] >= 0.75 else (BLUE if p["prob"] >= 0.6 else GREY)
    txt = (f"[b]{esc(m['home'])} – {esc(m['away'])}[/b]\n"
           f"[size=13sp][color={GREY}]{sport} · {esc(m['league'])} · {B.local_time(m)}[/color][/size]\n"
           f"Σημείο: [b][size=18sp]{esc(p['sign'])}[/size][/b]  ({esc(p['name'])})\n"
           f"Πιθανότητα: [b][color={color}]{pct(p['prob'])}[/color][/b] · δίκαιη απόδοση [b]{num(p['fair_odds'])}[/b]")
    if extra:
        mp, rs, rl, why = extra
        if mp is not None:
            txt += f"\nΜοντέλο: [b]{pct(mp)}[/b] (αγορά {pct(p['prob'])})"
        txt += (f"\nΑξιοπιστία: [b][color={REL_COLOR[rl]}]{rl} ({rs}/100)[/color][/b]"
                + (f" [size=12sp][color={GREY}]· {esc(', '.join(why))}[/color][/size]" if why else ""))
    if show_best and p.get("best"):
        txt += f"\nΚαλύτερη απόδοση αγοράς: [b]{num(p['best'])}[/b] · αξία [color={GREEN}]+{pct(p['ev'])}[/color]"
    return Card(text=txt)


class StoiximaApp(App):
    title = "Stoixima"

    def build(self):
        B.set_dir(self.user_data_dir)
        self.s = {**B.DEFAULTS, "bankroll": 100.0, "risk": "Συντηρητικό", "week_limit": 10, "use_model": True,
                  **B.load_settings()}
        self.models = B._read("models.json", {})
        self.slip_mode = "Κανονικό"
        self.busy = False
        self.root_w = Root()
        sm = self.root_w.ids.sm
        sm.transition = NoTransition()
        self.cols = {}
        for name in ("std", "slip", "value", "history", "settings"):
            scr = Screen(name=name)
            sv, col = column()
            scr.add_widget(sv)
            sm.add_widget(scr)
            self.cols[name] = col
        self._build_settings(self.cols["settings"])
        self.refresh()
        cache = B.load_cache()
        stale = True
        if cache.get("updated"):
            try:
                t = datetime.datetime.strptime(cache["updated"], "%d/%m/%Y %H:%M")
                stale = datetime.datetime.now() - t > datetime.timedelta(hours=6)
            except ValueError:
                pass
        if stale:
            Clock.schedule_once(lambda dt: self.update(), 0.8)
        return self.root_w

    def show(self, name):
        self.root_w.ids.sm.current = name
        if name == "history":
            self.show_history(check=True)

    # ------------------------------------------------------------ ανάλυση
    def enrich(self, items):
        out = []
        for m, p in items:
            mp = M.model_prob(self.models, m, p["sign"]) if self.s.get("use_model") else None
            rs, rl, why = M.reliability(m, p, mp)
            out.append((m, p, (mp, rs, rl, why)))
        return out

    def make_slip(self, ups):
        if self.slip_mode == "Ελληνικό":
            greek = [m for m in ups if M.is_greek(m)]
            stds = B.standards(greek, self.s)
            relaxed = False
            if len(stds) < int(self.s["slip"]):
                stds = B.standards(greek, {**self.s, "min_prob": 50})
                relaxed = True
        else:
            stds = B.standards(ups, self.s)
            relaxed = False
        rich = self.enrich(stds)
        good = [x for x in rich if x[2][1] >= 45 and not x[1].get("double")]
        rest = [x for x in rich if x not in good and not x[1].get("double")]
        pool = sorted(good, key=lambda x: -x[1]["prob"]) + sorted(rest, key=lambda x: -x[1]["prob"])
        chosen = pool[: max(1, int(self.s["slip"]))]
        prob, fair = 1.0, 1.0
        for _, p, _ in chosen:
            prob *= p["prob"]
            fair *= p["fair_odds"]
        return chosen, prob, fair, relaxed

    # ------------------------------------------------------------ οθόνες
    def refresh(self):
        cache = B.load_cache()
        ups = B.upcoming(cache, self.s)
        if cache.get("updated"):
            self.root_w.ids.msg.text = (f"{len(ups)} αγώνες τις επόμενες {self.s['hours']} ώρες · ενημέρωση "
                                        f"{cache['updated']}")
        stds = self.enrich(B.standards(ups, self.s))

        col = self.cols["std"]
        col.clear_widgets()
        col.add_widget(Plain(text=f"[size=17sp][b]Τα πιο πιθανά σημεία[/b][/size]\n[size=12sp]Ένα σημείο ανά αγώνα, "
                                  f"με πιθανότητα τουλάχιστον {self.s['min_prob']}%. Δίπλα: τι λέει το στατιστικό "
                                  f"μοντέλο και πόσο αξιόπιστη είναι η εκτίμηση.[/size]"))
        for m, p, ex in stds:
            col.add_widget(pick_card(m, p, extra=ex))
        if not stds:
            col.add_widget(Plain(text="Δεν βρέθηκαν σημεία με αυτό το όριο. Πάτα ΕΝΗΜΕΡΩΣΗ ή χαμήλωσε την "
                                      "ελάχιστη πιθανότητα στις Ρυθμίσεις."))
        col.add_widget(Plain(text=FOOT))
        self.show_slip(ups)

        col = self.cols["value"]
        col.clear_widgets()
        vp = self.enrich(B.value_picks(ups, self.s))
        col.add_widget(Plain(text="[size=17sp][b]Αποδόσεις με αξία[/b][/size]\n[size=12sp]Σημεία όπου κάποια εταιρεία "
                                  "δίνει απόδοση πάνω από τη δίκαιη. Είναι ο μόνος τρόπος με θετική προσδοκία, αλλά "
                                  "χάνουν συχνά. Έλεγξε αν και το δικό σου πρακτορείο δίνει τόσο.[/size]"))
        for m, p, ex in vp:
            col.add_widget(pick_card(m, p, show_best=True, extra=ex))
        if not vp:
            col.add_widget(Plain(text="Δεν βρέθηκαν αποδόσεις με αξία αυτή τη στιγμή."))
        col.add_widget(Plain(text=FOOT))
        if self.root_w.ids.sm.current == "history":
            self.show_history()

    def show_slip(self, ups=None):
        if ups is None:
            ups = B.upcoming(B.load_cache(), self.s)
        col = self.cols["slip"]
        col.clear_widgets()
        modes = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6), padding=(dp(8), dp(4)))
        for mode in ("Κανονικό", "Ελληνικό"):
            on = mode == self.slip_mode
            b = Button(text=f"{mode.upper()} ΔΕΛΤΙΟ", bold=True, background_normal="",
                       background_color=(0.95, 0.71, 0.14, 1) if on else (0.85, 0.86, 0.88, 1),
                       color=(0.11, 0.14, 0.2, 1))
            b.bind(on_release=lambda w, md=mode: self._set_mode(md))
            modes.add_widget(b)
        col.add_widget(modes)
        chosen, prob, fair, relaxed = self.make_slip(ups)
        title = "Ελληνικοί αγώνες" if self.slip_mode == "Ελληνικό" else "Τα πιο πιθανά σημεία"
        col.add_widget(Plain(text=f"[size=17sp][b]Προτεινόμενο δελτίο ({len(chosen)} αγώνες)[/b][/size]\n"
                                  f"[size=12sp]{title}, με προτίμηση σε όσα έχουν αξιοπιστία τουλάχιστον μέτρια."
                                  f"{' Δεν υπήρχαν αρκετοί αγώνες πάνω από το όριο, οπότε χαμήλωσε στο 50%.' if relaxed else ''}"
                                  f"[/size]"))
        if not chosen:
            msg = ("Δεν υπάρχουν ελληνικοί αγώνες στο διάστημα που έχεις ορίσει. Αύξησε τις ώρες στις Ρυθμίσεις "
                   "(π.χ. 168) ή πάτα ΕΝΗΜΕΡΩΣΗ." if self.slip_mode == "Ελληνικό" else "Δεν υπάρχουν ακόμη σημεία.")
            col.add_widget(Plain(text=msg))
            col.add_widget(Plain(text=FOOT))
            return
        for m, p, ex in chosen:
            col.add_widget(pick_card(m, p, extra=ex))
        col.add_widget(Card(text=f"[b]Πιθανότητα να βγει ΟΛΟ το δελτίο: [color={BLUE}][size=20sp]{pct(prob)}"
                                 f"[/size][/color][/b]\nΔίκαιη συνολική απόδοση: [b]{num(fair)}[/b]\n"
                                 f"[size=13sp]Αν ο ΟΠΑΠ δίνει συνολική απόδοση πάνω από {num(fair)}, το δελτίο έχει "
                                 f"αξία. Αν δίνει λιγότερο, μακροπρόθεσμα χάνεις.[/size]"))
        # διαχείριση κεφαλαίου
        col.add_widget(Plain(text=f"[b]Πόσα να ποντάρω[/b]  [size=12sp][color={GREY}]Κεφάλαιο τώρα: "
                                  f"{num(M.bankroll_now(self.s))} € · προφίλ {self.s.get('risk')}[/color][/size]"))
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6), padding=(dp(8), 0))
        odds_in = TextInput(hint_text="Συνολική απόδοση ΟΠΑΠ", input_filter="float", multiline=False)
        stake_in = TextInput(hint_text="Ποσό €", input_filter="float", multiline=False)
        row.add_widget(odds_in)
        row.add_widget(stake_in)
        col.add_widget(row)
        advice = Plain(text="")
        col.add_widget(advice)

        def recalc(*a):
            try:
                o = float(odds_in.text.replace(",", ".")) if odds_in.text else None
            except ValueError:
                o = None
            st, note, left = M.suggest_stake(self.s, prob, o)
            stake_in.text = f"{st:g}"
            advice.text = (f"Πρόταση: [b]{num(st)} €[/b]. {esc(note)}\n[size=12sp][color={GREY}]Όριο εβδομάδας: "
                           f"απομένουν {num(left)} €.[/color][/size]")
        odds_in.bind(text=recalc)
        recalc()
        save = Button(text="ΑΠΟΘΗΚΕΥΣΗ ΣΤΟ ΙΣΤΟΡΙΚΟ", bold=True, size_hint_y=None, height=dp(52),
                      background_normal="", background_color=(0.06, 0.48, 0.31, 1))

        def do_save(*a):
            try:
                st = float(stake_in.text.replace(",", ".") or 0)
                o = float(odds_in.text.replace(",", ".")) if odds_in.text else fair
            except ValueError:
                return
            M.add_slip([M.pick_record(m, p, ex[0], ex[1]) for m, p, ex in chosen], st, o, self.slip_mode)
            save.text = "ΑΠΟΘΗΚΕΥΤΗΚΕ. Θα ελεγχθεί αυτόματα."
            save.disabled = True
        save.bind(on_release=do_save)
        col.add_widget(save)
        col.add_widget(Plain(text=FOOT))

    def _set_mode(self, mode):
        self.slip_mode = mode
        self.show_slip()

    # ------------------------------------------------------------ ιστορικό
    def show_history(self, check=False):
        col = self.cols["history"]
        col.clear_widgets()
        st = M.stats()
        bank = M.bankroll_now(self.s)
        pcol = GREEN if st["profit"] >= 0 else RED
        txt = (f"[size=17sp][b]Ιστορικό και αποτελέσματα[/b][/size]\n"
               f"Κεφάλαιο τώρα: [b]{num(bank)} €[/b] (αρχικό {num(float(self.s.get('bankroll', 100)))} €)\n"
               f"Κέρδος/ζημιά: [b][color={pcol}]{'+' if st['profit'] >= 0 else ''}{num(st['profit'])} €[/color][/b]"
               f" από {num(st['staked'])} € που παίχτηκαν\n"
               f"Δελτία: {st['won']} κερδισμένα από {st['settled']} που κρίθηκαν · σύνολο {st['slips']}\n"
               f"Αυτή την εβδομάδα: {num(M.week_spent())} € από όριο "
               f"{num(bank * float(self.s.get('week_limit', 10)) / 100)} €")
        col.add_widget(Card(text=txt))
        if st["buckets"]:
            lines = []
            for lo, (n, w, ps) in st["buckets"].items():
                lines.append(f"Σημεία {lo}–{lo + 10}%: βγήκαν [b]{w}/{n}[/b] ({pct(w / n)}) · αναμενόταν "
                             f"{pct(ps / n)}")
            col.add_widget(Card(text="[b]Πόσο σωστές βγήκαν οι πιθανότητες[/b]\n" + "\n".join(lines) +
                                     f"\n[size=12sp][color={GREY}]Με λίγα σημεία οι αριθμοί αλλάζουν πολύ. Χρειάζονται "
                                     f"δεκάδες για ασφαλές συμπέρασμα.[/color][/size]"))
        chk = Button(text="ΕΛΕΓΧΟΣ ΑΠΟΤΕΛΕΣΜΑΤΩΝ", bold=True, size_hint_y=None, height=dp(50),
                     background_normal="", background_color=(0.95, 0.71, 0.14, 1), color=(0.11, 0.14, 0.2, 1))
        chk.bind(on_release=lambda *a: self.settle(chk))
        col.add_widget(chk)
        slips = M.load_slips()
        if not slips:
            col.add_widget(Plain(text="Δεν έχεις αποθηκεύσει ακόμα δελτία. Στην καρτέλα Δελτίο πάτα "
                                      "«ΑΠΟΘΗΚΕΥΣΗ ΣΤΟ ΙΣΤΟΡΙΚΟ»."))
        for sl in slips[:60]:
            stc = {"κέρδισε": GREEN, "χάθηκε": RED}.get(sl["status"], BLUE)
            lines = []
            for pk in sl["picks"]:
                mark = ("[color=#0F7B4F][b]ΝΑΙ[/b][/color]" if pk.get("won") else "[color=#B4461B][b]ΟΧΙ[/b][/color]") \
                    if pk.get("won") is not None else "[color=#6B7486]…[/color]"
                res = f" ({pk['result']})" if pk.get("result") else ""
                lines.append(f"{mark} {esc(pk['home'])} – {esc(pk['away'])}: [b]{esc(pk['sign'])}[/b] "
                             f"{pct(pk['prob'])}{res}")
            ret = f" · επιστροφή {num(sl['stake'] * sl['odds'])} €" if sl["status"] == "κέρδισε" and sl.get("odds") else ""
            card = Card(text=f"[b][color={stc}]{STATUS_TXT.get(sl['status'], sl['status'])}[/color][/b] · {sl['kind']} · {sl['date']}\n"
                             f"Ποσό {num(sl['stake'])} € · απόδοση {num(sl['odds'] or 0)}{ret}\n" + "\n".join(lines))
            col.add_widget(card)
            dl = Button(text="Διαγραφή", size_hint_y=None, height=dp(36), background_normal="",
                        background_color=(0.85, 0.86, 0.88, 1), color=(0.11, 0.14, 0.2, 1))
            dl.bind(on_release=lambda w, sid=sl["id"]: (M.delete_slip(sid), self.show_history()))
            col.add_widget(dl)
        if check and any(s["status"] == "εκκρεμεί" for s in slips):
            self.settle(chk)

    def settle(self, btn=None):
        if self.busy:
            return
        self.busy = True
        if btn:
            btn.text = "Έλεγχος…"

        def log(m):
            Clock.schedule_once(lambda dt: setattr(self.root_w.ids.msg, "text", m))

        def work():
            try:
                n = M.settle_all(log)
                msg = f"Ενημερώθηκαν {n} αποτελέσματα." if n else ("Δεν υπάρχουν ακόμα νέα αποτελέσματα "
                                                                   "(τα ποδοσφαιρικά ανεβαίνουν 2 φορές την εβδομάδα).")
            except Exception as e:  # noqa: BLE001
                msg = "Σφάλμα ελέγχου: " + str(e)[:80]
            Clock.schedule_once(lambda dt: done(msg))

        def done(msg):
            self.busy = False
            self.show_history()
            self.root_w.ids.msg.text = msg

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ ρυθμίσεις
    def _build_settings(self, col):
        s = self.s
        col.padding = (dp(14), dp(8))
        col.spacing = dp(6)
        col.add_widget(Plain(text="[size=17sp][b]Ρυθμίσεις[/b][/size]\n[size=13sp]Δεν χρειάζεται εγγραφή. "
                                  "Ποδόσφαιρο: ~40 πρωταθλήματα (football-data.co.uk, ενημέρωση 2 φορές την εβδομάδα). "
                                  "Μπάσκετ: NBA, NCAA, WNBA (ESPN).[/size]"))

        def row(label, widget):
            b = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
            b.add_widget(Label(text=label, color=(0.11, 0.14, 0.2, 1), halign="left", valign="middle",
                               text_size=(Window.width * 0.58, None), size_hint_x=0.62))
            widget.size_hint_x = 0.38
            b.add_widget(widget)
            col.add_widget(b)

        self.fb = CheckBox(active=s["football"], color=(0.11, 0.14, 0.2, 1))
        self.bb = CheckBox(active=s["basketball"], color=(0.11, 0.14, 0.2, 1))
        self.ou = CheckBox(active=s["overunder"], color=(0.11, 0.14, 0.2, 1))
        self.um = CheckBox(active=s.get("use_model", True), color=(0.11, 0.14, 0.2, 1))
        row("Ποδόσφαιρο", self.fb)
        row("Μπάσκετ", self.bb)
        row("Και Over/Under 2,5 γκολ", self.ou)
        row("Στατιστικό μοντέλο (περισσότερα δεδομένα)", self.um)
        self.hours = Spinner(text=str(s["hours"]), values=["24", "48", "72", "120", "168"])
        row("Αγώνες των επόμενων ωρών", self.hours)
        self.minp = Spinner(text=str(s["min_prob"]), values=["55", "60", "65", "70", "75", "80", "85"])
        row("Ελάχιστη πιθανότητα «σταντάρ» (%)", self.minp)
        self.slip = Spinner(text=str(s["slip"]), values=["1", "2", "3", "4", "5", "6"])
        row("Αγώνες στο δελτίο", self.slip)
        col.add_widget(Plain(text="[b]Διαχείριση κεφαλαίου[/b]"))
        self.bank = TextInput(text=f"{float(s.get('bankroll', 100)):g}", input_filter="float", multiline=False)
        row("Αρχικό κεφάλαιο (€)", self.bank)
        self.risk = Spinner(text=s.get("risk", "Συντηρητικό"), values=list(M.RISK))
        row("Προφίλ ρίσκου", self.risk)
        self.wl = Spinner(text=str(s.get("week_limit", 10)), values=["5", "10", "15", "20", "30"])
        row("Όριο εβδομάδας (% κεφαλαίου)", self.wl)
        save = Button(text="ΑΠΟΘΗΚΕΥΣΗ", bold=True, size_hint_y=None, height=dp(50), background_normal="",
                      background_color=(0.95, 0.71, 0.14, 1), color=(0.11, 0.14, 0.2, 1))
        save.bind(on_release=lambda *a: self._save())
        col.add_widget(save)
        col.add_widget(Plain(text=FOOT))

    def _save(self):
        old_need = (self.s["football"], self.s["basketball"], self.s["hours"], self.s.get("use_model"))
        try:
            bank = float(self.bank.text.replace(",", "."))
        except ValueError:
            bank = 100.0
        self.s.update(football=self.fb.active, basketball=self.bb.active, overunder=self.ou.active,
                      use_model=self.um.active, hours=int(self.hours.text), min_prob=int(self.minp.text),
                      slip=int(self.slip.text), bankroll=bank, risk=self.risk.text, week_limit=int(self.wl.text))
        B.save_settings(self.s)
        self.refresh()
        if (self.s["football"], self.s["basketball"], self.s["hours"], self.s["use_model"]) != old_need:
            self.update()
        else:
            self.root_w.ids.msg.text = "Οι ρυθμίσεις αποθηκεύτηκαν."

    # ------------------------------------------------------------ ενημέρωση
    def update(self):
        if self.busy:
            return
        self.busy = True
        up = self.root_w.ids.upd
        up.disabled = True
        up.text = "…"

        def log(m):
            Clock.schedule_once(lambda dt: setattr(self.root_w.ids.msg, "text", m))

        def work():
            err = None
            try:
                data = B.fetch_all(self.s, log)
                if data.get("notes"):
                    err = "Μερική ενημέρωση: " + data["notes"][0]
                if self.s.get("use_model"):
                    ups = B.upcoming(data, self.s)
                    self.models = M.build_models(ups, log)
                    B._write("models.json", self.models)
            except Exception as e:  # noqa: BLE001
                err = "Σφάλμα: " + str(e)
            Clock.schedule_once(lambda dt: self._done(err))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, err):
        self.busy = False
        up = self.root_w.ids.upd
        up.disabled = False
        up.text = "ΕΝΗΜΕΡΩΣΗ"
        self.refresh()
        if err:
            self.root_w.ids.msg.text = err[:140]


if __name__ == "__main__":
    StoiximaApp().run()
