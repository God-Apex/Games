using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;

namespace ApexKasino
{
    // režim CEO: manažeři, kteří kasino řídí za hráče
    partial class GameForm
    {
        static readonly string[] MgrTitle = { "Provozní ředitel", "Architekt", "Finanční ředitel", "Manažer událostí" };
        static readonly string[] MgrName = { "Hana Dvořáková", "Petr Stavinoha", "Karel Kubíček", "Lenka Veselá" };
        static readonly int[] MgrWage = { 1200, 1800, 1500, 800 };
        static readonly string[] MgrDesc = {
            "Najímá a propouští techniky, uklízeče a ochranku podle provozu.",
            "Staví automaty, stoly, služby i dekorace a drží uličky volné.",
            "Kupuje vylepšení, rozšiřuje sál, otevírá patra a pouští kampaně.",
            "Rozhoduje o událostech za tebe, hra se kvůli nim nezastaví."
        };
        static readonly Color[] MgrSuit = { Color.FromArgb(40, 60, 110), Color.FromArgb(120, 80, 40), Color.FromArgb(30, 30, 36), Color.FromArgb(150, 40, 90) };
        static readonly int[] Reserves = { 10000, 30000, 80000 };

        readonly bool[] mgr = new bool[4];
        readonly string[] mgrLast = new string[4];
        float ceoReserve = 10000, teamT;
        bool archBlocked;   // architekt nenašel místo – finanční ředitel má rozšířit sál
        readonly List<Note> teamLog = new List<Note>();

        // tým nikdy neutratí pod zvolenou rezervu ani pod 1,5 denních nákladů
        float DailyCosts()
        {
            float w = MgrWages() + upkeepSum;
            foreach (var s in staff) w += RoleWage[s.Role];
            return w;
        }
        float Reserve { get { return Math.Max(ceoReserve, DailyCosts() * 1.5f); } }

        bool CeoMode { get { return mgr[0] && mgr[1] && mgr[2] && mgr[3]; } }
        int MgrWages() { int w = 0; for (int i = 0; i < 4; i++) if (mgr[i]) w += MgrWage[i]; return w; }

        void ResetTeam()
        {
            for (int i = 0; i < 4; i++) { mgr[i] = false; mgrLast[i] = null; }
            ceoReserve = 10000; teamT = 0; teamLog.Clear();
        }

        void SetMgr(int i, bool on)
        {
            if (mgr[i] == on) return;
            mgr[i] = on;
            TeamLog(i, on ? "nastupuje do práce" : "odchází z firmy");
        }

        void SetCeo(bool on)
        {
            for (int i = 0; i < 4; i++) SetMgr(i, on);
            if (on) { ShowBanner("REŽIM CEO", "Tým teď řídí kasino za tebe. Můžeš zrychlit čas a sledovat, jak roste."); Sfx(sGoal); }
        }

        void TeamLog(int who, string what)
        {
            mgrLast[who] = what;
            teamLog.Add(new Note { T = MgrTitle[who] + ": " + what, C = MgrSuit[who], When = "D" + day + " " + TimeStr() });
            if (teamLog.Count > 40) teamLog.RemoveAt(0);
        }

        string TeamSaveLine(CultureInfo ci)
        {
            return string.Format(ci, "M {0} {1} {2} {3} {4}", mgr[0] ? 1 : 0, mgr[1] ? 1 : 0, mgr[2] ? 1 : 0, mgr[3] ? 1 : 0, ceoReserve);
        }

        void TeamLoad(string[] p, CultureInfo ci)
        {
            for (int i = 0; i < 4; i++) mgr[i] = p[1 + i] == "1";
            ceoReserve = float.Parse(p[5], ci);
        }

        void TeamTick(float dt, float dmin)
        {
            if (demo) return;
            teamT -= dmin;
            if (teamT > 0) return;
            teamT = 30;
            var keep = CF;
            if (mgr[0]) OpsTick();
            if (mgr[2]) CfoTick();
            if (mgr[1]) ArchitectTick();
            CF = keep;
        }

        // ---------- provozní ředitel ----------

        void OpsTick()
        {
            int games = 0, slots = 0;
            foreach (var o in AllObjs()) { if (o.T.IsGame) games++; if (o.T.Kind == ObjKind.Slot) slots++; }
            if (games == 0) return;
            int floorsUsed = 0;
            foreach (var fl in floors) if (fl.Objs.Count > 0) floorsUsed++;
            int[] want = {
                Math.Max(floorsUsed, (int)Math.Ceiling(games / 20.0)) + (BrokenCount() >= 3 && StaffCount(0) < games / 8 ? 1 : 0),
                guests.Count == 0 ? 0 : Math.Max(floorsUsed, (int)Math.Ceiling(guests.Count / 24.0)) + (LitterTotal() > 40 ? 1 : 0),
                slots >= 25 || (slots >= 12 && cheatsLost > cheatsCaught) ? 1 + slots / 40 : 0
            };
            bool broke = money < Reserve;
            for (int r = 0; r < 3; r++)
            {
                int have = StaffCount(r);
                if (have < want[r] && have < 30 && !broke) { Hire(r); TeamLog(0, "najal: " + RoleName[r].ToLower() + " (" + (have + 1) + ")"); return; }
                if (have > want[r] + 1) { Fire(r); TeamLog(0, "propustil: " + RoleName[r].ToLower() + " (" + (have - 1) + ")"); return; }
            }
        }

        // ---------- finanční ředitel ----------

        float Occupancy(Floor fl)
        {
            var own = OwnLevels[fl.Own];
            int used = 0;
            foreach (var o in fl.Objs) used += o.W * o.H;
            return used / (float)(own.Width * own.Height);
        }

        void CfoTick()
        {
            float free = money - Reserve;
            // nejdřív musí kasino vydělávat: dost her a zisk za poslední den
            bool earning = history.Count > 0 && history[history.Count - 1].Operating > 0;
            if (gameSeats < 10) return;
            // rozšíření sálu má přednost, bez místa kasino neroste
            foreach (var fl in floors)
            {
                if (fl.Own >= 3 || (Occupancy(fl) < .22f && !archBlocked) || OwnCost[fl.Own + 1] > free) continue;
                CF = fl; Expand(); archBlocked = false;
                TeamLog(2, "rozšířil " + FloorNames[fl.Index].ToLower() + " za " + FormatKc(OwnCost[fl.Own]));
                return;
            }
            if (!earning && free < 150000) return;
            foreach (var id in new[] { "cash", "aircon", "shuffler", "clover", "loyalty", "vipclub" })
            {
                var u = ups.Find(x => x.Id == id);
                if (u == null || u.Owned || u.Stars > maxStars || u.Cost > free) continue;
                if (id == "shuffler" && CountKind(ObjKind.Table) == 0) continue;
                BuyUp(u); TeamLog(2, "koupil " + u.Name + " za " + FormatKc(u.Cost));
                return;
            }
            foreach (var fl in floors)
            {
                if (fl.Own >= 3 || Occupancy(fl) < .28f || OwnCost[fl.Own + 1] > free) continue;
                CF = fl; Expand();
                TeamLog(2, "rozšířil " + FloorNames[fl.Index].ToLower() + " za " + FormatKc(OwnCost[fl.Own]));
                return;
            }
            int n = floors.Count;
            if (n < 3 && maxStars >= FloorStars[n] && FloorCost[n] <= free)
            {
                bool full = true;
                foreach (var fl in floors) if (fl.Own < 3) full = false;
                if (full || archBlocked) { archBlocked = false; BuyFloor(); TeamLog(2, "otevřel " + FloorNames[n].ToLower() + " za " + FormatKc(FloorCost[n])); return; }
            }
            if (campaignMin <= 0 && gameSeats >= 10 && guests.Count < gameSeats * .5f && free > 8000)
            {
                StartCampaign(); TeamLog(2, "spustil reklamní kampaň (málo hostů)");
            }
        }

        void BuyFloor()
        {
            int n = floors.Count;
            if (n >= 3) return;
            if (maxStars < FloorStars[n]) { Note(FloorNames[n] + " se odemkne od " + FloorStars[n] + " " + StarWord(FloorStars[n]) + ".", Pal.Red); Sfx(sErr); return; }
            if (money < FloorCost[n]) { Note("Na " + FloorNames[n].ToLower() + " potřebuješ " + FormatKc(FloorCost[n]) + ".", Pal.Red); Sfx(sErr); return; }
            for (int x = 16; x <= 17; x++)
                for (int y = 16; y <= 17; y++)
                    if (floors[0].Occ[x, y] != null) { Note("Uvolni v přízemí místo pro eskalátor (vpravo od vchodu).", Pal.Red); Sfx(sErr); return; }
            money -= FloorCost[n]; today.Build += FloorCost[n];
            floors.Add(new Floor { Index = n });
            RecomputeMaps();
            floorDirty = true;
            Note(FloorNames[n] + " je otevřené. Eskalátor vede z přízemí.", Pal.Cyan);
            ShowBanner("NOVÉ PATRO", FloorNames[n] + " je otevřené – přepni se na něj dole vlevo na mapě.");
            Sfx(sGoal);
        }

        // ---------- architekt ----------

        void ArchitectTick()
        {
            float free = money - Reserve;
            if (free < 1500) return;
            int pref; bool wait;
            var t = PickBuild(out pref, out wait);
            // na důležitou věc se šetří; jen když hostům výrazně chybí místa, postaví se levný automat
            if (t != null && CostOf(t) > free && (!wait || guests.Count > gameSeats * 1.2f)) { t = GameToBuild(free); pref = -1; }
            if (t == null || CostOf(t) > free || t.Stars > maxStars) return;
            Floor bf = null; int bx = 0, by = 0, bdir = 0;
            for (int attempt = 0; attempt < 2 && bf == null; attempt++)
            {
                if (attempt == 1)
                {
                    // pro velkou věc není místo: zkusí aspoň automat a dá vědět, že je potřeba prostor
                    archBlocked = true;
                    var alt = GameToBuild(free);
                    if (alt == null || alt == t) return;
                    t = alt; pref = -1;
                }
                foreach (var fl in floors)
                {
                    if (pref >= 0 && fl.Index != pref) continue;
                    if (t.IsGame && NeedsServices(fl)) continue;   // místo nech pro toalety a bar
                    int x, y, d;
                    CF = fl;
                    if (FindSpot(t, out x, out y, out d)) { bf = fl; bx = x; by = y; bdir = d; break; }
                }
            }
            if (bf == null) return;
            if (t.W * t.H > 1) archBlocked = false;
            CF = bf;
            Place(t, bx, by, bdir, false);
            TeamLog(1, "postavil " + t.Name + " (" + FloorNames[bf.Index].ToLower() + ") za " + FormatKc(CostOf(t)));
        }

        ObjType Best(Cat cat, ObjKind kind, float free, bool byBet)
        {
            ObjType best = null;
            foreach (var t in Catalog.All)
            {
                if (t.Kind != kind || t.Stars > maxStars || CostOf(t) > free) continue;
                if (best == null || (byBet ? t.Bet > best.Bet : t.Attract > best.Attract)) best = t;
            }
            return best;
        }

        // co postavit teď; pref = patro, kam to patří (-1 kamkoli); wait = na tuhle věc se vyplatí našetřit
        ObjType PickBuild(out int pref, out bool wait)
        {
            pref = -1; wait = false;
            float free = money - Reserve;
            // toalety a bar na každém patře podle počtu hostů
            foreach (var fl in floors)
            {
                int games = 0, wc = 0, bar = 0, here = 0;
                foreach (var o in fl.Objs) { if (o.T.IsGame) games++; if (o.T.Kind == ObjKind.Wc) wc++; if (o.T.Kind == ObjKind.Bar) bar++; }
                foreach (var gu in guests) if (gu.Floor == fl.Index) here++;
                if (games >= 3 && wc < 1 + here / 16) { pref = fl.Index; wait = true; return Catalog.Get("wc"); }
                if (games >= 5 && bar < 1 + here / 15) { pref = fl.Index; wait = true; return Catalog.Get("bar"); }
            }
            int area = 0; foreach (var fl in floors) { var r = OwnLevels[fl.Own]; area += r.Width * r.Height; }
            if (CountKind(ObjKind.Bin) < area / 45 && gameSeats > 6)
            {
                int most = 0;
                foreach (var fl in floors) if (fl.Litter.Count >= floors[most].Litter.Count) most = fl.Index;
                pref = most; return Catalog.Get("bin");
            }
            // požadavky na další hvězdu
            int next = StarsNow() + 1;
            if (next <= 5)
                foreach (var r in StarReqs(next, false))
                {
                    if (r.Value) continue;
                    string k = r.Key;
                    wait = true;
                    if (k.StartsWith("Místa")) { wait = false; return GameToBuild(free); }
                    if (k.StartsWith("Bar")) return Catalog.Get("bar");
                    if (k.StartsWith("Toalety")) return Catalog.Get("wc");
                    if (k.StartsWith("Aspoň jeden stůl")) return Catalog.Get("blackjack");
                    if (k.StartsWith("Bankomat")) return Catalog.Get("atm");
                    if (k.StartsWith("Pohovka")) return Catalog.Get("sofa");
                    if (k.StartsWith("Jackpot")) return Catalog.Get("island");
                    if (k.StartsWith("Socha")) return Catalog.Get("statue");
                    if (k.StartsWith("Dva různé"))
                        foreach (var id in new[] { "blackjack", "roulette", "poker" })
                            if (CountId(id) == 0 && Catalog.Get(id).Stars <= maxStars) return Catalog.Get(id);
                    if (k.StartsWith("Dekorace")) { wait = false; return BestDecor(free); }
                }
            wait = false;
            if (DecorSum() < gameSeats * .5f) return BestDecor(free);
            if (guests.Count >= gameSeats * .7f || gameSeats < 12) return GameToBuild(free);
            if (DecorSum() < gameSeats * .9f) return BestDecor(free);
            if (CountKind(ObjKind.Atm) < 1 + guests.Count / 80) return Catalog.Get("atm");
            if (CountKind(ObjKind.Sofa) < 1 + guests.Count / 60) return Catalog.Get("sofa");
            return null;
        }

        // nejlepší dekorace, kterou si tým může dovolit
        ObjType BestDecor(float free)
        {
            ObjType best = null;
            foreach (var t in Catalog.All)
            {
                if (t.Kind != ObjKind.Decor || t.Stars > maxStars || CostOf(t) > free) continue;
                if (best == null || t.Attract > best.Attract) best = t;
            }
            return best ?? Catalog.Get("plant");
        }
        bool NeedsServices(Floor fl)
        {
            int games = 0, wc = 0, bar = 0, here = 0;
            foreach (var o in fl.Objs) { if (o.T.IsGame) games++; if (o.T.Kind == ObjKind.Wc) wc++; if (o.T.Kind == ObjKind.Bar) bar++; }
            foreach (var gu in guests) if (gu.Floor == fl.Index) here++;
            return (games >= 3 && wc < 1 + here / 16) || (games >= 5 && bar < 1 + here / 15);
        }

        ObjType GameToBuild(float free)
        {
            int tables = CountKind(ObjKind.Table);
            if (gameSeats >= 16 && rng.NextDouble() < .15 && tables < 1 + gameSeats / 25)
            {
                var tb = Best(Cat.Stoly, ObjKind.Table, free, true);
                if (tb != null) return tb;
            }
            // náhodně jeden ze tří nejdražších dostupných automatů
            var list = new List<ObjType>();
            foreach (var t in Catalog.All)
                if (t.Kind == ObjKind.Slot && t.Stars <= maxStars && CostOf(t) <= free && !(t.Id == "retro" && gameSeats >= 12)) list.Add(t);
            if (list.Count == 0) return null;
            list.Sort((a, b) => b.Bet.CompareTo(a.Bet));
            return list[rng.Next(Math.Min(3, list.Count))];
        }

        // místo podle vzoru: řady automatů zády k sobě, uličky každý 4. řádek a každý 7. sloupec
        bool FindSpot(ObjType t, out int bx, out int by, out int bdir)
        {
            bx = by = bdir = 0;
            var own = OwnLevels[ownLevel];
            float cx = own.X + own.Width / 2f, cy = own.Y + own.Height / 2f;
            var org = Origin;
            double best = double.MinValue;
            bool found = false;
            for (int y = own.Y; y < own.Bottom; y++)
                for (int x = own.X; x < own.Right; x++)
                {
                    int ry = y - own.Y;
                    int dir;
                    if (t.H == 2) { if (ry % 4 != 1) continue; dir = 0; }
                    else if (ry % 4 == 1) dir = t.Rot ? 2 : 0;
                    else if (ry % 4 == 2) dir = 0;
                    else continue;
                    var d = Dims(t, dir);
                    bool aisle = false;
                    for (int i = 0; i < d.Width; i++) if ((x + i - own.X) % 7 == 0) aisle = true;
                    if (aisle || x + d.Width > own.Right - 1 || y + d.Height > own.Bottom) continue;
                    double sc;
                    float mx = x + d.Width / 2f, my = y + d.Height / 2f;
                    if (t.IsGame) sc = -Math.Abs(mx - cx) - Math.Abs(my - cy) * 1.2;
                    else if (t.Kind == ObjKind.Decor)
                    {
                        int seats = 0;
                        foreach (var o in objs) if (o.T.IsGame && Math.Abs(o.X - mx) + Math.Abs(o.Y - my) < 5) seats += o.Seats.Length;
                        sc = seats - decor[Math.Min(GW - 1, (int)mx), Math.Min(GH - 1, (int)my)] * .6;
                    }
                    else sc = -(Math.Abs(mx - org.X) + Math.Abs(my - org.Y)) * .5 - (Math.Abs(mx - org.X) < 3 ? 6 : 0);
                    if (sc <= best) continue;
                    if (Validate(t, x, y, dir) != null) continue;
                    best = sc; bx = x; by = y; bdir = dir; found = true;
                }
            return found;
        }

        int AutoChoice(GameEvent ev)
        {
            float free = money - Reserve;
            switch (ev.Title)
            {
                case "Firemní večírek APEX": return free > 15000 ? 0 : 1;
                case "Pokerový turnaj": return free > 36000 && CountKind(ObjKind.Table) >= 2 ? 0 : 1;
                case "Výpadek proudu": return free > 6000 && gameSeats >= 12 ? 0 : 1;
                case "Influencerka chce natáčet": return rating >= 60 ? 0 : 1;
                case "Stížnost souseda": return money > 3000 ? 0 : 1;
                case "Slavný host": return free > 4000 ? 0 : 1;
                default: return 0;
            }
        }

        // ---------- záložka Vedení ----------

        void DrawTeamTab(Graphics g)
        {
            float y = 106;
            var hero = new RectangleF(936, y, 320, 92);
            FillRound(g, B(CeoMode ? Color.FromArgb(40, 60, 30) : Pal.Panel2), hero, 8);
            if (CeoMode) DrawRound(g, P(Pal.Yellow, 1.5f), hero, 8);
            Txt(g, "Režim CEO", F(15, true), Pal.Yellow, 946, y + 8);
            TxtWrap(g, CeoMode ? "Celý tým pracuje. Kasino se řídí samo – zrychli čas a sleduj výsledky." : "Najmi celý tým a kasino se bude řídit samo. Ty jen sleduješ a sbíráš zisk.",
                F(10.5f, false), Pal.Muted, new RectangleF(946, y + 30, 200, 60));
            Button(g, new RectangleF(1150, y + 12, 98, 34), CeoMode ? "Propustit" : "Zapnout", () => SetCeo(!CeoMode), CeoMode ? 3 : 1, true);
            Txt(g, FormatKc(MgrWage[0] + MgrWage[1] + MgrWage[2] + MgrWage[3]) + "/den", F(9.5f, false), Pal.Dim, 1152, y + 52);

            y += 100;
            Txt(g, "Rezerva: tým neutratí pod " + FormatKc(Reserve), F(10.5f, true), Pal.Text, 938, y + 5);
            if (Reserve > ceoReserve) Txt(g, "(1,5 denních nákladů)", F(9, false), Pal.Dim, 1130, y + 30);
            for (int i = 0; i < 3; i++)
            {
                int k = i;
                Button(g, new RectangleF(938 + i * 62, y + 24, 58, 24), (Reserves[i] / 1000) + " tis.", () => { ceoReserve = Reserves[k]; }, ceoReserve == Reserves[i] ? 1 : 0, true);
            }
            y += 56;
            for (int i = 0; i < 4; i++)
            {
                int k = i;
                var r = new RectangleF(936, y, 320, 70);
                FillRound(g, B(Pal.Panel2), r, 8);
                var ib = new RectangleF(942, y + 8, 40, 40);
                FillRound(g, B(Color.FromArgb(4, 14, 32)), ib, 6);
                var st = g.Save();
                g.TranslateTransform(ib.X + 20, ib.Y + 24); g.ScaleTransform(2f, 2f);
                Person(g, 0, 0, 0, 1, 0, MgrSuit[i], Color.FromArgb(230, 190, 150), Color.FromArgb(60, 40, 30), false);
                g.Restore(st);
                Txt(g, MgrTitle[i], F(12, true), mgr[i] ? Color.White : Pal.Muted, 990, y + 5);
                Txt(g, MgrName[i] + " · " + FormatKc(MgrWage[i]) + "/den", F(9.5f, false), Pal.Dim, 990, y + 22);
                string line = mgr[i] ? (mgrLast[i] != null ? "Naposledy: " + mgrLast[i] : "Pracuje…") : MgrDesc[i];
                TxtWrap(g, line, F(9.5f, false), mgr[i] ? Pal.Cream : Pal.Muted, new RectangleF(990, y + 36, 180, 32));
                Button(g, new RectangleF(1178, y + 20, 72, 28), mgr[i] ? "Propustit" : "Najmout", () => SetMgr(k, !mgr[k]), mgr[i] ? 0 : 1, true);
                y += 76;
            }
            y += 2;
            Txt(g, "CO TÝM UDĚLAL", F(9.5f, true), Pal.Yellow, 938, y);
            y += 16;
            int n = Math.Min(4, teamLog.Count);
            if (n == 0) Txt(g, "Zatím nic – najmi někoho z vedení.", F(10, false), Pal.Dim, 938, y);
            for (int i = 0; i < n; i++)
            {
                var nt = teamLog[teamLog.Count - 1 - i];
                TxtClip(g, nt.When + "  " + nt.T, F(9.5f, i == 0), i == 0 ? Pal.Text : Pal.Muted, new RectangleF(938, y + i * 15, 316, 15));
            }
        }
    }
}
