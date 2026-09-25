using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Text;

namespace ApexKasino
{
    // simulace: čas, hosté, personál, ekonomika, stavění, cíle, ukládání
    partial class GameForm
    {
        const int GW = 28, GH = 18;
        const float MinPerSec = 8f;
        const float PoolSeed = 5000;   // základ jackpotu po výhře; hradí ho výhoda kasina (viz PlayRound)   // herní minuty za sekundu při rychlosti 1×

        static readonly Rectangle[] OwnLevels = {
            new Rectangle(8, 8, 12, 10), new Rectangle(5, 5, 18, 13), new Rectangle(2, 2, 24, 16), new Rectangle(0, 0, 28, 18)
        };
        static readonly int[] OwnCost = { 0, 35000, 90000, 200000 };
        static readonly string[] RoleName = { "Technik", "Uklízeč", "Ochranka" };
        static readonly int[] RoleWage = { 1200, 800, 1500 };
        static readonly string[] FirstNames = {
            "Petr", "Jana", "Tomáš", "Lucie", "Martin", "Eva", "Jakub", "Tereza", "Pavel", "Klára", "Ondřej", "Veronika",
            "Lukáš", "Markéta", "David", "Hana", "Filip", "Monika", "Jiří", "Alena", "Radek", "Zuzana", "Michal",
            "Kateřina", "Adam", "Barbora", "Karel", "Simona", "Vojtěch", "Lenka", "Roman", "Ivana", "Marek", "Petra"
        };
        const string Initials = "NKDSVHPMBRČŠTJLZ";
        static readonly Color[] Shirts = {
            Color.FromArgb(200, 60, 80), Color.FromArgb(70, 130, 200), Color.FromArgb(90, 170, 110), Color.FromArgb(150, 90, 190),
            Color.FromArgb(230, 140, 50), Color.FromArgb(225, 225, 232), Color.FromArgb(60, 64, 76), Color.FromArgb(40, 150, 160),
            Color.FromArgb(180, 50, 130), Color.FromArgb(120, 100, 70)
        };
        static readonly Color[] Skins = { Color.FromArgb(241, 204, 170), Color.FromArgb(224, 172, 130), Color.FromArgb(176, 122, 84), Color.FromArgb(112, 76, 52) };
        static readonly Color[] Hairs = { Color.FromArgb(40, 28, 20), Color.FromArgb(90, 60, 30), Color.FromArgb(200, 160, 90), Color.FromArgb(150, 150, 150), Color.FromArgb(120, 40, 20), Color.FromArgb(20, 20, 24) };

        readonly Random rng = new Random();
        // patra; CF je patro, se kterým se právě pracuje (hráčův pohled nebo patro zpracovávaného hosta)
        readonly List<Floor> floors = new List<Floor>();
        Floor CF;
        int viewFloor;
        static readonly int[] FloorCost = { 0, 120000, 280000 };
        static readonly int[] FloorStars = { 0, 2, 4 };
        static readonly string[] FloorNames = { "Přízemí", "1. patro", "2. patro" };

        List<Obj> objs { get { return CF.Objs; } }
        Obj[,] occ { get { return CF.Occ; } }
        List<PointF> litter { get { return CF.Litter; } }
        int[,] litterGrid { get { return CF.LitterGrid; } }
        float[,] decor { get { return CF.Decor; } }
        bool[,] binNear { get { return CF.BinNear; } }
        int ownLevel { get { return CF.Own; } set { CF.Own = value; } }
        Floor ViewF { get { return floors[viewFloor]; } }

        IEnumerable<Obj> AllObjs()
        {
            foreach (var fl in floors) foreach (var o in fl.Objs) yield return o;
        }

        int LitterTotal() { int n = 0; foreach (var fl in floors) n += fl.Litter.Count; return n; }
        List<Guest> guests = new List<Guest>();
        List<Staff> staff = new List<Staff>();
        readonly int[] fdist = new int[GW * GH], fprev = new int[GW * GH], fqueue = new int[GW * GH];

        float money, minutes, rating, pool, campaignMin, hourAcc, attractTotal, bestDayProfit, goalCheckT;
        int day, leftCount, totalGuests, maxStars, goalIdx, cheatsCaught, cheatsLost, gameSeats, upkeepSum;
        bool demo, bankrupt;
        DayStats today = new DayStats();
        readonly List<DayStats> history = new List<DayStats>();
        readonly List<Upgrade> ups = new List<Upgrade>();
        readonly List<Goal> goals = new List<Goal>();
        readonly List<Note> notes = new List<Note>();
        DayStats report; float reportT;
        string banner, bannerSub; float bannerT;
        float lastBreakNote = -99, lastWinSound = -99;

        string saveDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "APEX Kasino");
        string SavePath { get { return Path.Combine(saveDir, "save.txt"); } }

        // ---------- nová hra ----------

        void NewGame(bool demoMode)
        {
            floors.Clear(); floors.Add(new Floor()); CF = floors[0]; viewFloor = 0;
            guests.Clear(); staff.Clear();
            money = 60000; minutes = 12 * 60; day = 1;
            ResetTeam();
            rating = 45; leftCount = 0; totalGuests = 0; maxStars = 1; goalIdx = 0; pool = PoolSeed; campaignMin = 0; hourAcc = 0;
            cheatsCaught = cheatsLost = 0; bestDayProfit = 0;
            today = new DayStats { Day = 1 }; history.Clear(); notes.Clear();
            report = null; banner = null; bankrupt = false;
            demo = demoMode;
            InitUps(); InitGoals();
            ClearSelection(); tool = null; sellTool = false; moveTool = false; carry = null; ResetEvents();
            if (demo) BuildDemo();
            RecomputeMaps();
            floorDirty = true;
            if (!demo)
            {
                Note("Vítej v APEX Kasinu! Postav první automaty z panelu vpravo.", Pal.Cream);
                Note("Nech před automaty volné místo – tam sedí hráči.", Pal.Muted);
            }
        }

        void BuildDemo()
        {
            ownLevel = 2; maxStars = 5; money = 1000000; rating = 74; leftCount = 30;
            foreach (var u in ups) u.Owned = true;
            for (int x = 4; x <= 11; x++) { DemoPlace("classic", x, 3, 0); DemoPlace("pyramid", x, 6, 2); }
            DemoPlace("island", 14, 3, 0);
            DemoPlace("roulette", 18, 3, 0);
            DemoPlace("station", 22, 3, 0);
            DemoPlace("blackjack", 18, 8, 0);
            DemoPlace("poker", 22, 8, 0);
            DemoPlace("bar", 4, 10, 0);
            DemoPlace("sofa", 8, 10, 0);
            DemoPlace("atm", 11, 10, 0);
            DemoPlace("wc", 22, 14, 0);
            DemoPlace("fountain", 13, 9, 0);
            DemoPlace("statue", 4, 14, 0);
            DemoPlace("led", 8, 14, 0);
            for (int x = 15; x <= 20; x++) { DemoPlace("pyramid", x, 12, 2); DemoPlace("classic", x, 13, 0); }
            foreach (var p in new[] { new Point(3, 8), new Point(12, 8), new Point(11, 14), new Point(2, 16), new Point(25, 16), new Point(2, 3), new Point(16, 8) })
                DemoPlace("plant", p.X, p.Y, 0);
            DemoPlace("palm", 25, 12, 0); DemoPlace("palm", 7, 16, 0);
            DemoPlace("bin", 12, 11, 0); DemoPlace("bin", 17, 16, 0);
            Hire(0); Hire(1); Hire(2);
            RecomputeMaps();
            for (int i = 0; i < 28; i++)
            {
                var g = SpawnGuest();
                for (int k = 0; k < 40; k++)
                {
                    int x = rng.Next(3, 25), y = rng.Next(3, 17);
                    if (Walkable(x, y)) { g.X = x + .5f; g.Y = y + .5f; break; }
                }
                Release(g); Decide(g);
            }
            money = 1000000;
        }

        void DemoPlace(string id, int x, int y, int dir)
        {
            var t = Catalog.Get(id);
            if (Validate(t, x, y, dir) == null) Place(t, x, y, dir, true);
        }

        void InitUps()
        {
            ups.Clear();
            AddUp("clover", "Clover Link jackpot", 40000, 2, "Propojí automaty do progresivního jackpotu. Automaty lákají o 20 % víc.");
            AddUp("cash", "Chytrá pokladna", 25000, 1, "Hosté si dobijí kredit přímo u automatu a utratí o 25 % víc.");
            AddUp("shuffler", "Míchačka karet APEX", 18000, 1, "Stoly odehrají hru o 30 % rychleji.");
            AddUp("aircon", "Klimatizace", 15000, 1, "Hosté se méně unaví a jsou spokojenější.");
            AddUp("loyalty", "Věrnostní program", 35000, 3, "Každý den přijde o 30 % víc hostů.");
            AddUp("vipclub", "VIP klub", 60000, 4, "Chodí víc VIP hostů s rozpočtem v desítkách tisíc.");
        }

        void AddUp(string id, string name, int cost, int stars, string desc)
        {
            ups.Add(new Upgrade { Id = id, Name = name, Cost = cost, Stars = stars, Desc = desc });
        }

        bool Has(string id)
        {
            foreach (var u in ups) if (u.Id == id) return u.Owned;
            return false;
        }

        void InitGoals()
        {
            goals.Clear();
            AddGoal("Postav 4 automaty", () => CountKind(ObjKind.Slot) >= 4, () => CountKind(ObjKind.Slot) + " / 4", 5000);
            AddGoal("Najmi technika (záložka Personál)", () => StaffCount(0) >= 1, null, 3000);
            AddGoal("Postav bar", () => CountKind(ObjKind.Bar) >= 1, null, 4000);
            AddGoal("Postav toalety", () => CountKind(ObjKind.Wc) >= 1, null, 4000);
            AddGoal("Obsluž 60 hostů", () => totalGuests >= 60, () => totalGuests + " / 60", 6000);
            AddGoal("Najmi uklízeče a postav koš", () => StaffCount(1) >= 1 && CountKind(ObjKind.Bin) >= 1, null, 4000);
            AddGoal("Dosáhni hodnocení 2 hvězdy", () => maxStars >= 2, null, 10000);
            AddGoal("Rozšiř herní sál (záložka Vylepšení)", () => ownLevel >= 1, null, 10000);
            AddGoal("Postav blackjack nebo ruletu", () => CountKind(ObjKind.Table) >= 1, null, 15000);
            AddGoal("Najmi někoho z vedení (záložka Vedení)", () => mgr[0] || mgr[1] || mgr[2] || mgr[3], null, 8000);
            AddGoal("Měj v kasinu 35 hostů najednou", () => guests.Count >= 35, () => guests.Count + " / 35", 20000);
            AddGoal("Dosáhni hodnocení 3 hvězdy", () => maxStars >= 3, null, 25000);
            AddGoal("Otevři 1. patro (záložka Vylepšení)", () => floors.Count >= 2, null, 40000);
            AddGoal("Postav Jackpot Island", () => CountId("island") >= 1, null, 30000);
            AddGoal("Vydělej za den 60 000 Kč provozního zisku", () => Math.Max(bestDayProfit, today.Operating) >= 60000,
                () => FormatKc(Math.Max(bestDayProfit, today.Operating)) + " / 60 000 Kč", 40000);
            AddGoal("Dosáhni hodnocení 4 hvězdy", () => maxStars >= 4, null, 50000);
            AddGoal("Hodnota kasina 1 000 000 Kč", () => CasinoValue() >= 1000000, () => FormatKc(CasinoValue()) + " / 1 000 000 Kč", 100000);
            AddGoal("Dosáhni hodnocení 5 hvězd", () => maxStars >= 5, null, 100000);
        }

        void AddGoal(string text, Func<bool> done, Func<string> progress, int reward)
        {
            goals.Add(new Goal { Text = text, Done = done, Progress = progress, Reward = reward });
        }

        // ---------- hlavní krok ----------

        void Step(float dt)
        {
            if (bankrupt) return;
            float dmin = dt * MinPerSec;
            float prev = minutes;
            minutes += dmin;
            if (minutes >= 1440) minutes -= 1440;
            if (prev < 360 && minutes >= 360) DayEnd();
            hourAcc += dmin;
            if (hourAcc >= 60) { hourAcc -= 60; HourTick(); }
            if (campaignMin > 0) campaignMin = Math.Max(0, campaignMin - dmin);
            UpdateEffects(dt, dmin);

            float frac = dmin / 1440f, wages = 0;
            foreach (var s in staff) wages += RoleWage[s.Role];
            wages += MgrWages();
            float up = upkeepSum * frac, wg = wages * frac;
            if (!demo) { money -= up + wg; today.Upkeep += up; today.Wages += wg; }

            CF = floors[0];
            Spawn(dt);
            for (int i = 0; i < guests.Count; i++) { CF = floors[guests[i].Floor]; UpdateGuest(guests[i], dt); }
            guests.RemoveAll(g => g.Gone);
            if (selGuest != null && selGuest.Gone) selGuest = null;
            for (int i = 0; i < staff.Count; i++) { CF = floors[staff[i].Floor]; UpdateStaff(staff[i], dt); }
            CF = floors[0];
            TeamTick(dt, dmin);
            CF = ViewF;
            foreach (var o in AllObjs())
            {
                o.Anim += dt;
                for (int i = 0; i < o.Spin.Length; i++) if (o.Spin[i] > 0) o.Spin[i] -= dt;
            }

            int st = StarsNow();
            if (st > maxStars)
            {
                maxStars = st;
                if (!demo) StarsUnlocked(st);
            }

            goalCheckT -= dt;
            if (goalCheckT <= 0) { goalCheckT = .5f; CheckGoals(); }
            if (!demo && money < -30000) { bankrupt = true; Sfx(sLose); }
        }

        void StarsUnlocked(int st)
        {
            var names = new List<string>();
            foreach (var t in Catalog.All) if (t.Stars == st) names.Add(t.Name);
            foreach (var u in ups) if (u.Stars == st) names.Add(u.Name);
            string sub = names.Count > 0 ? "Odemčeno: " + string.Join(", ", names.ToArray()) : "Hosté si tvoje kasino chválí.";
            ShowBanner("HODNOCENÍ " + st + " " + StarWord(st).ToUpper(), sub);
            Note("Kasino má " + st + " " + StarWord(st) + ". " + sub, Pal.Yellow);
            Sfx(sGoal);
        }

        void CheckGoals()
        {
            if (demo) return;
            while (goalIdx < goals.Count && goals[goalIdx].Done())
            {
                var gl = goals[goalIdx];
                money += gl.Reward; today.Rewards += gl.Reward;
                Note("Cíl splněn: " + gl.Text + " (+" + FormatKc(gl.Reward) + ")", Pal.Yellow);
                ShowBanner("CÍL SPLNĚN", gl.Text + "  ·  odměna " + FormatKc(gl.Reward));
                Sfx(sGoal);
                goalIdx++;
                if (gl.Text.StartsWith("Hodnota kasina"))
                    ShowBanner("KASINO SNŮ", "Milion na kontě kasina. Tohle by se v Litvínovicích líbilo!");
            }
        }

        void ShowBanner(string title, string sub) { banner = title; bannerSub = sub; bannerT = 4.5f; }

        void HourTick()
        {
            MaybeEvent();
            if (demo) return;
            int slots = CountKind(ObjKind.Slot);
            if (slots == 0) return;
            if (rng.NextDouble() < .01 + slots * .0015)
            {
                int sec = StaffCount(2);
                if (sec > 0 && rng.NextDouble() < .55 + .15 * sec)
                {
                    cheatsCaught++; rating = Math.Min(100, rating + 1);
                    Note("Ochranka chytila podvodníka u automatu.", Pal.Green);
                }
                else
                {
                    float loss = (float)Math.Round((1000 + rng.NextDouble() * (1000 + slots * 150)) / 100) * 100;
                    money -= loss; today.Events += loss; cheatsLost++;
                    Note("Podvodník obral automat o " + FormatKc(loss) + (sec == 0 ? ". Najmi ochranku." : "."), Pal.Red);
                    Sfx(sErr);
                }
            }
        }

        void DayEnd()
        {
            if (!demo)
            {
                today.Day = day;
                history.Add(today);
                if (history.Count > 30) history.RemoveAt(0);
                bestDayProfit = Math.Max(bestDayProfit, today.Operating);
                report = today; reportT = 9;
                Note("Den " + day + " uzavřen: provozní zisk " + FormatKc(today.Operating), today.Operating >= 0 ? Pal.Green : Pal.Red);
                Sfx(sDay);
            }
            foreach (var o in AllObjs()) o.IncomeToday = 0;
            day++;
            today = new DayStats { Day = day };
            if (!demo) Save(true);
        }

        // ---------- hosté ----------

        void Spawn(float dt)
        {
            if (gameSeats == 0) return;
            float h = minutes / 60f;
            float curve = h < 6 ? .8f : h < 12 ? .35f : h < 17 ? .7f : h < 20 ? 1f : 1.35f;
            float lam = .12f * (1 + attractTotal / 25f) * curve * (.6f + StarsNow() * .15f);
            if (Has("loyalty")) lam *= 1.3f;
            if (campaignMin > 0) lam *= 1.6f;
            int cap = (int)(gameSeats * 1.4f) + 8;
            if (guests.Count >= cap) return;
            if (rng.NextDouble() < lam * dt) { var g = SpawnGuest(); Decide(g); }
        }

        Guest SpawnGuest()
        {
            var g = new Guest();
            g.X = (rng.Next(2) == 0 ? 13 : 14) + .5f; g.Y = 17.5f; g.FaceY = -1;
            g.Name = FirstNames[rng.Next(FirstNames.Length)] + " " + Initials[rng.Next(Initials.Length)] + ".";
            g.Vip = rng.NextDouble() < (Has("vipclub") ? .1 : .03) + (vipBoostMin > 0 ? .25 : 0);
            float b = g.Vip ? 15000 + (float)rng.NextDouble() * 30000 : 600 + (float)(Math.Pow(rng.NextDouble(), 2) * 4400);
            if (Has("cash")) b *= 1.25f;
            g.Money = g.Budget = (float)Math.Round(b / 100) * 100;
            g.Shirt = Shirts[rng.Next(Shirts.Length)]; g.Skin = Skins[rng.Next(Skins.Length)]; g.Hair = Hairs[rng.Next(Hairs.Length)];
            g.Happy = 68 + (float)rng.NextDouble() * 12;
            g.Thirst = (float)rng.NextDouble() * 30; g.Bladder = (float)rng.NextDouble() * 30;
            g.Energy = 80 + (float)rng.NextDouble() * 20;
            g.State = GS.Walk;
            guests.Add(g); totalGuests++; today.Guests++;
            return g;
        }

        void UpdateGuest(Guest g, float dt)
        {
            if (g.Gone) return;
            g.VisitT += dt;
            if (g.ThoughtT > 0) g.ThoughtT -= dt;
            int tx = Clamp((int)g.X, 0, GW - 1), ty = Clamp((int)g.Y, 0, GH - 1);

            if (g.State != GS.Leave)
            {
                g.Thirst += .8f * dt; g.Bladder += .55f * dt;
                g.Energy -= (Has("aircon") ? .24f : .34f) * dt;
                float h = MoodAt(tx, ty);
                int lit = LitterAround(tx, ty);
                if (g.Thirst > 85) h -= .3f;
                if (g.Bladder > 85) h -= .4f;
                if (g.State == GS.Use && g.Target != null && g.Target.T.IsGame) h += .12f;
                g.Happy = Math.Max(0, Math.Min(100, g.Happy + h * dt));
                if (lit >= 2 && g.ThoughtT <= 0 && rng.NextDouble() < dt * .05) Think(g, "Tady je nepořádek…", 2);
            }

            switch (g.State)
            {
                case GS.Walk:
                    {
                        int r = StepPath(g, 2.3f, dt);
                        if (r == 1) Arrive(g);
                        else if (r == 2) { Release(g); Decide(g); }
                        else if (rng.NextDouble() < dt * .007 * (binNear[tx, ty] ? .2 : 1)) DropLitter(g);
                        break;
                    }
                case GS.Use:
                    UseTick(g, dt);
                    break;
                case GS.Leave:
                    {
                        int r = StepPath(g, 2.3f, dt);
                        if (r == 1)
                        {
                            if (g.Floor != 0) { ChangeFloor(g, 0); GoExit(g); }
                            else GuestGone(g);
                        }
                        else if (r == 2) GoExit(g);
                        break;
                    }
            }
        }

        // přesun po eskalátoru na jiné patro
        void ChangeFloor(Agent a, int fl)
        {
            a.Floor = fl; a.TravelTo = -1;
            CF = floors[fl];
            a.X = (a.X >= 17 ? 17 : 16) + .5f; a.Y = 17.5f;
            a.Path = null; a.PathI = 0;
        }

        // cesta k eskalátoru (fdist musí být spočítané od agenta)
        bool GoEscalator(Agent a, int target)
        {
            if (target < 0 || target >= floors.Count || target == a.Floor) return false;
            int d1 = fdist[17 * GW + 16], d2 = fdist[17 * GW + 17];
            if (d1 < 0 && d2 < 0) return false;
            int ex = (d2 >= 0 && (d1 < 0 || d2 < d1)) ? 17 : 16;
            a.Path = PathTo(ex, 17) ?? new List<Point>(); a.PathI = 0;
            a.TravelTo = target;
            return true;
        }

        // jiné patro, kde je volné místo u objektu, který splňuje podmínku
        int FloorWith(Guest g, Func<Obj, bool> pred)
        {
            int start = rng.Next(floors.Count);
            for (int k = 0; k < floors.Count; k++)
            {
                var fl = floors[(start + k) % floors.Count];
                if (fl.Index == g.Floor) continue;
                foreach (var o in fl.Objs)
                {
                    if (!pred(o)) continue;
                    foreach (var u in o.Users) if (u == null) return fl.Index;
                }
            }
            return -1;
        }

        bool GoFloor(Guest g, int target)
        {
            if (!GoEscalator(g, target)) return false;
            g.Target = null; g.Seat = -1; g.State = GS.Walk;
            return true;
        }

        void Arrive(Guest g)
        {
            if (g.TravelTo >= 0) { ChangeFloor(g, g.TravelTo); Decide(g); return; }
            var o = g.Target;
            if (o == null) { Decide(g); return; }
            if (!objs.Contains(o) || g.Seat < 0 || o.Users[g.Seat] != g || (o.T.Breaks && o.Broken)) { Release(g); Decide(g); return; }
            g.State = GS.Use;
            float cx = o.X + o.W / 2f, cy = o.Y + o.H / 2f;
            float dx = cx - g.X, dy = cy - g.Y, d = (float)Math.Sqrt(dx * dx + dy * dy);
            if (d > 0) { g.FaceX = dx / d; g.FaceY = dy / d; }
            if (o.T.IsGame)
            {
                g.PlayT = .4f; g.Plays = 0;
                g.PlaysGoal = o.T.Kind == ObjKind.Slot ? rng.Next(10, 36) : rng.Next(5, 16);
            }
            else
            {
                g.Timer = o.T.UseTime * (.8f + (float)rng.NextDouble() * .4f);
                if (o.T.Kind == ObjKind.Wc) g.Hidden = true;
            }
        }

        void UseTick(Guest g, float dt)
        {
            var o = g.Target;
            if (o == null || !objs.Contains(o)) { Release(g); Decide(g); return; }
            if (o.T.IsGame)
            {
                if (o.Broken) { Release(g); g.Happy -= 8; Think(g, "Automat se rozbil!", 2); Decide(g); return; }
                g.PlayT -= dt;
                if (g.PlayT <= 0)
                {
                    float iv = o.T.Interval;
                    if (o.T.Kind == ObjKind.Table && Has("shuffler")) iv *= .7f;
                    g.PlayT = iv * (.85f + (float)rng.NextDouble() * .3f);
                    PlayRound(g, o);
                }
                if (g.Plays >= g.PlaysGoal || g.Money < o.T.Bet || g.Bladder > 80 || g.Thirst > 78 || g.Energy < 22)
                {
                    Release(g); Decide(g);
                }
            }
            else
            {
                g.Timer -= dt;
                if (g.Timer <= 0) { FinishService(g, o); Release(g); Decide(g); }
            }
        }

        void PlayRound(Guest g, Obj o)
        {
            float bet = o.T.Bet;
            if (g.Money < bet) return;
            g.Money -= bet; g.Plays++; o.Plays++;
            float pay = 0; bool jack = false;
            int seat = Math.Max(0, g.Seat);
            if (o.T.Kind == ObjKind.Slot)
            {
                bool clover = Has("clover");
                bool island = o.T.Id == "island";
                double pj; float m;
                if (clover) { pool += bet * .02f; pj = island ? .004 : .0008; m = (1 - o.T.Edge - .02f - (float)pj * PoolSeed / bet) / .3f; }
                else { pj = island ? .003 : .0012; m = (1 - o.T.Edge - (float)pj * 80) / .3f; }
                double r = rng.NextDouble();
                if (r < pj) { jack = true; if (clover) { pay = pool; pool = PoolSeed; } else pay = bet * 80; }
                else if (r < pj + .3) pay = bet * m * (.4f + (float)rng.NextDouble() * 1.2f);

                if (seat < o.Spin.Length)
                {
                    o.Spin[seat] = .6f;
                    int b = seat * 3;
                    if (jack) { o.Reels[b] = o.Reels[b + 1] = o.Reels[b + 2] = 0; }
                    else if (pay > 0) { int s = 1 + rng.Next(4); o.Reels[b] = o.Reels[b + 1] = o.Reels[b + 2] = s; }
                    else
                    {
                        o.Reels[b] = rng.Next(5); o.Reels[b + 1] = rng.Next(5);
                        do { o.Reels[b + 2] = rng.Next(5); } while (o.Reels[b + 2] == o.Reels[b] && o.Reels[b] == o.Reels[b + 1]);
                    }
                }
            }
            else if (rng.NextDouble() < .47) pay = bet * (1 - o.T.Edge) / .47f;

            pay = (float)Math.Round(pay / 10) * 10;
            g.Money += pay; g.Won += pay - bet;
            float net = bet - pay;
            if (!demo)
            {
                money += net;
                if (o.T.Kind == ObjKind.Slot) today.Slots += net; else today.Tables += net;
            }
            o.IncomeToday += net; o.IncomeTotal += net;

            if (pay > 0) g.Happy = Math.Min(100, g.Happy + (pay > bet * 3 ? 3 : .8f));
            else g.Happy -= .15f;

            float wx = o.X + o.W / 2f, wy = o.Y;
            if (jack)
            {
                g.Happy = 100;
                Think(g, "JACKPOT! Tomu nevěřím!", 3);
                rating = Math.Min(100, rating + 1.5f);
                if (!demo) Note("Jackpot " + FormatKc(pay) + " na " + o.T.Name + " – vyhrává " + g.Name + "!", Pal.Yellow);
                Confetti(wx, wy + .5f, 50);
                Float(wx, wy, "JACKPOT " + FormatKc(pay), Pal.Yellow);
                Sfx(sJack);
            }
            else if (pay >= bet * 6)
            {
                Float(wx, wy, "+" + FormatKc(pay), Pal.Cream);
                Coins(wx, wy + .4f, 8);
                if (realT - lastWinSound > 1.2f) { lastWinSound = realT; Sfx(sWin); }
                if (g.ThoughtT <= 0) Think(g, "Výhra! Dneska je můj den.", 3);
            }

            if (sturdyMin <= 0 && rng.NextDouble() < o.T.Break)
            {
                o.Broken = true;
                if (!demo && realT - lastBreakNote > 6)
                {
                    lastBreakNote = realT;
                    Note("Porucha: " + o.T.Name + (StaffCount(0) == 0 ? " – najmi technika!" : ""), Pal.Red);
                    Sfx(sBreak);
                }
            }
        }

        void FinishService(Guest g, Obj o)
        {
            switch (o.T.Kind)
            {
                case ObjKind.Bar:
                    if (g.Money >= o.T.Price)
                    {
                        g.Money -= o.T.Price;
                        if (!demo) { money += o.T.Price; today.Bar += o.T.Price; }
                        o.IncomeToday += o.T.Price; o.IncomeTotal += o.T.Price; o.Plays++;
                        g.Thirst = 0; g.Happy = Math.Min(100, g.Happy + 4);
                        if (rng.NextDouble() < .3) Float(o.X + o.W / 2f, o.Y, "+" + o.T.Price + " Kč", Pal.Green);
                    }
                    else { g.Thirst = 40; Think(g, "Nemám ani na drink…", 2); }
                    break;
                case ObjKind.Wc:
                    g.Bladder = 0; g.Hidden = false; g.Happy = Math.Min(100, g.Happy + 2); o.Plays++;
                    break;
                case ObjKind.Atm:
                    {
                        float w = (float)Math.Round((1000 + rng.NextDouble() * 3000) * (g.Vip ? 5 : 1) / 100) * 100;
                        g.Money += w; g.UsedAtm = true; o.Plays++;
                        if (!demo) { money += o.T.Price; today.Atm += o.T.Price; }
                        o.IncomeToday += o.T.Price; o.IncomeTotal += o.T.Price;
                        Think(g, "Ještě jedno kolo!", 4);
                        break;
                    }
                case ObjKind.Sofa:
                    g.Energy = Math.Min(100, g.Energy + 55); g.Happy = Math.Min(100, g.Happy + 3); o.Plays++;
                    break;
            }
        }

        void Decide(Guest g)
        {
            if (g.State == GS.Leave || g.Gone) return;
            Release(g);
            Flood(Clamp((int)g.X, 0, GW - 1), Clamp((int)g.Y, 0, GH - 1));

            if (g.Energy < 12) { GoHome(g, "Jsem unavený, jdu domů."); return; }
            if (g.Happy < 15) { GoHome(g, "Tady mě to nebaví."); return; }
            if (g.VisitT > 420) { GoHome(g, "Už je čas jít domů."); return; }

            if (g.Bladder > 72)
            {
                if (GoService(g, ObjKind.Wc) || GoFloor(g, FloorWith(g, o => o.T.Kind == ObjKind.Wc))) return;
                // toalety existují, jen jsou obsazené: chvíli počká
                if (CountKind(ObjKind.Wc) > 0 && g.Bladder < 95) { g.Happy -= 1; if (g.ThoughtT <= 0) Think(g, "Fronta na toaletu…", 1); Wander(g); return; }
                if (g.NoWc) { GoHome(g, "Nemají tu ani toalety!"); return; }
                g.NoWc = true; g.Happy -= 15; Think(g, "Kde jsou tu toalety?!", 1);
            }
            if (g.Thirst > 70)
            {
                if (GoService(g, ObjKind.Bar) || GoFloor(g, FloorWith(g, o => o.T.Kind == ObjKind.Bar))) return;
                if (CountKind(ObjKind.Bar) > 0 && g.Thirst < 92) { if (g.ThoughtT <= 0) Think(g, "U baru je plno…", 0); }
                else
                if (!g.NoBar) { g.NoBar = true; g.Happy -= 8; Think(g, "Rád bych se něčeho napil…", 0); }
                g.Thirst = 55;
            }
            if (g.Energy < 35 && GoService(g, ObjKind.Sofa)) return;

            if (g.Money < MinBet())
            {
                if (!g.UsedAtm && g.Happy > 55 && GoService(g, ObjKind.Atm)) return;
                GoHome(g, g.Won > 0 ? "Odcházím s výhrou!" : "Došly mi peníze.");
                return;
            }
            // občas zkusí jiné patro, i když je tady volno
            Func<Obj, bool> game = o => o.T.IsGame && !o.Broken && o.T.Bet <= g.Money;
            if (floors.Count > 1 && rng.NextDouble() < .3 && GoFloor(g, FloorWith(g, game))) { g.Waits = 0; return; }
            if (GoGame(g) || GoFloor(g, FloorWith(g, game))) { g.Waits = 0; return; }
            g.Waits++; g.Happy -= 4;
            if (g.Waits > 3) { GoHome(g, "Nemám kde hrát, všechno je obsazené."); return; }
            if (g.ThoughtT <= 0) Think(g, "Všechno je obsazené…", 2);
            Wander(g);
        }

        float MinBet()
        {
            float m = float.MaxValue;
            foreach (var o in AllObjs()) if (o.T.IsGame && !o.Broken && o.T.Bet < m) m = o.T.Bet;
            return m == float.MaxValue ? 100 : m;
        }

        bool SeatFree(Obj o, int i)
        {
            var s = o.Seats[i];
            return o.Users[i] == null && InGrid(s.X, s.Y) && Walkable(s.X, s.Y) && fdist[s.Y * GW + s.X] >= 0;
        }

        bool GoService(Guest g, ObjKind kind)
        {
            Obj best = null; int bestSeat = -1, bestD = int.MaxValue;
            foreach (var o in objs)
            {
                if (o.T.Kind != kind) continue;
                for (int i = 0; i < o.Seats.Length; i++)
                {
                    if (!SeatFree(o, i)) continue;
                    int d = fdist[o.Seats[i].Y * GW + o.Seats[i].X];
                    if (d < bestD) { bestD = d; best = o; bestSeat = i; }
                }
            }
            if (best == null) return false;
            SendTo(g, best, bestSeat);
            return true;
        }

        bool GoGame(Guest g)
        {
            Obj best = null; int bestSeat = -1; double bestScore = double.MinValue;
            bool clover = Has("clover");
            foreach (var o in objs)
            {
                if (!o.T.IsGame || o.Broken) continue;
                bool table = o.T.Kind == ObjKind.Table;
                if (o.T.Bet > g.Money / (table ? 4f : 2.5f) && o.T.Bet > g.Money) continue;
                if (o.T.Bet > g.Money) continue;
                for (int i = 0; i < o.Seats.Length; i++)
                {
                    if (!SeatFree(o, i)) continue;
                    int d = fdist[o.Seats[i].Y * GW + o.Seats[i].X];
                    double sc = o.T.Attract * .6 + rng.NextDouble() * 5 - d * .12;
                    if (clover && o.T.Kind == ObjKind.Slot) sc += 1;
                    if (g.Vip) sc += o.T.Bet / 100.0;
                    if (table && g.Money > 8000) sc += 3;
                    if (o.T.Bet > g.Money / 4f) sc -= 4;
                    if (sc > bestScore) { bestScore = sc; best = o; bestSeat = i; }
                    break;   // stačí první volné místo u stroje
                }
            }
            if (best == null) return false;
            SendTo(g, best, bestSeat);
            return true;
        }

        void SendTo(Guest g, Obj o, int seat)
        {
            o.Users[seat] = g;
            g.Target = o; g.Seat = seat; g.State = GS.Walk;
            g.Path = PathTo(o.Seats[seat].X, o.Seats[seat].Y); g.PathI = 0;
            if (g.Path == null) { Release(g); g.Path = new List<Point>(); }
        }

        void Wander(Guest g)
        {
            g.Target = null; g.Seat = -1; g.State = GS.Walk;
            var own = OwnLevels[ownLevel];
            for (int k = 0; k < 40; k++)
            {
                int x = own.X + rng.Next(own.Width), y = own.Y + rng.Next(own.Height);
                int d = fdist[y * GW + x];
                if (d >= 2 && d <= 10) { g.Path = PathTo(x, y); g.PathI = 0; return; }
            }
            g.Path = new List<Point>(); g.PathI = 0;
        }

        void GoHome(Guest g, string reason)
        {
            Release(g);
            g.State = GS.Leave;
            Think(g, reason, g.Happy < 40 ? 2 : -1);
            GoExit(g);
        }

        void GoExit(Guest g)
        {
            g.State = GS.Leave;
            Flood(Clamp((int)g.X, 0, GW - 1), Clamp((int)g.Y, 0, GH - 1));
            if (g.Floor != 0)
            {
                // z patra dolů eskalátorem; když cesta není, rovnou se přesune
                if (!GoEscalator(g, 0)) { g.Path = new List<Point>(); g.PathI = 0; }
                return;
            }
            int a = fdist[17 * GW + 13], b = fdist[17 * GW + 14];
            if (a < 0 && b < 0) { g.Path = new List<Point>(); g.PathI = 0; return; }
            int ex = (b >= 0 && (a < 0 || b < a)) ? 14 : 13;
            g.Path = PathTo(ex, 17); g.PathI = 0;
            if (g.Path == null) g.Path = new List<Point>();
        }

        void GuestGone(Guest g)
        {
            g.Gone = true;
            leftCount++;
            rating = rating * .93f + g.Happy * .07f;
        }

        void Release(Guest g)
        {
            var o = g.Target;
            if (o != null && g.Seat >= 0 && g.Seat < o.Users.Length && o.Users[g.Seat] == g) o.Users[g.Seat] = null;
            g.Target = null; g.Seat = -1; g.Hidden = false;
            if (g.State == GS.Use) g.State = GS.Walk;
        }

        void Think(Guest g, string text, int icon)
        {
            g.Thought = text; g.ThoughtT = 4; g.Icon = icon;
        }

        void DropLitter(Guest g)
        {
            if (litter.Count >= 150) return;
            int tx = Clamp((int)g.X, 0, GW - 1), ty = Clamp((int)g.Y, 0, GH - 1);
            if (!Walkable(tx, ty)) return;
            litter.Add(new PointF(g.X + (float)(rng.NextDouble() - .5) * .5f, g.Y + (float)(rng.NextDouble() - .5) * .5f));
            litterGrid[tx, ty]++;
        }

        // změna nálady hosta za sekundu na daném poli
        float MoodAt(int x, int y)
        {
            float h = -.07f + decor[x, y] * .02f;
            if (Has("aircon")) h += .03f;
            h -= Math.Min(3, LitterAround(x, y)) * .25f;
            return h;
        }

        int LitterAround(int x, int y)
        {
            int n = 0;
            for (int i = -1; i <= 1; i++)
                for (int j = -1; j <= 1; j++)
                    if (InGrid(x + i, y + j)) n += litterGrid[x + i, y + j];
            return n;
        }

        // ---------- personál ----------

        void Hire(int role)
        {
            if (StaffCount(role) >= 30) return;
            var s = new Staff { Role = role, X = 13.5f + rng.Next(2), Y = 17.5f, FaceY = -1, Floor = 0 };
            s.Name = FirstNames[rng.Next(FirstNames.Length)] + " " + Initials[rng.Next(Initials.Length)] + ".";
            staff.Add(s);
        }

        void Fire(int role)
        {
            for (int i = staff.Count - 1; i >= 0; i--)
            {
                if (staff[i].Role != role) continue;
                ReleaseJob(staff[i]);
                if (selStaff == staff[i]) selStaff = null;
                staff.RemoveAt(i);
                return;
            }
        }

        void ReleaseJob(Staff s)
        {
            if (s.Job != null && s.Job.Tech == s) s.Job.Tech = null;
            s.Job = null; s.HasLitter = false; s.Mode = 0;
        }

        void UpdateStaff(Staff s, float dt)
        {
            if (s.Mode == 2)
            {
                s.Timer -= dt;
                if (s.Job != null && !objs.Contains(s.Job)) { ReleaseJob(s); return; }
                if (s.Timer <= 0) FinishJob(s);
                return;
            }
            if (s.Mode == 1)
            {
                int r = StepPath(s, 2.6f, dt);
                if (r == 1)
                {
                    if (s.TravelTo >= 0) { ChangeFloor(s, s.TravelTo); s.Mode = 0; s.SearchT = 0; s.Timer = 1; return; }
                    if (s.Job != null || s.HasLitter) { s.Mode = 2; s.Timer = s.Role == 0 ? 3.5f : 1f; }
                    else { s.Mode = 0; s.Timer = 1 + (float)rng.NextDouble() * 3; }
                }
                else if (r == 2) { ReleaseJob(s); s.TravelTo = -1; }
                return;
            }
            s.Timer -= dt; s.SearchT -= dt;
            if (s.SearchT <= 0)
            {
                s.SearchT = .4f;
                if (s.Role == 0 && FindRepair(s)) return;
                if (s.Role == 1 && FindLitter(s)) return;
            }
            if (s.Timer <= 0) StaffWander(s);
        }

        bool FindRepair(Staff s)
        {
            bool any = false;
            foreach (var o in objs) if (o.Broken && o.Tech == null) { any = true; break; }
            if (!any)
            {
                // porucha na jiném patře, kam nikdo nejde
                foreach (var o in AllObjs())
                    if (o.Floor != s.Floor && o.Broken && o.Tech == null && !StaffHeading(0, o.Floor))
                        return TravelStaff(s, o.Floor);
                return false;
            }
            Flood(Clamp((int)s.X, 0, GW - 1), Clamp((int)s.Y, 0, GH - 1));
            Obj best = null; Point bp = Point.Empty; int bd = int.MaxValue;
            foreach (var o in objs)
            {
                if (!o.Broken || o.Tech != null) continue;
                foreach (var p in Around(o))
                {
                    int d = fdist[p.Y * GW + p.X];
                    if (d >= 0 && d < bd) { bd = d; best = o; bp = p; }
                }
            }
            if (best == null) return false;
            best.Tech = s; s.Job = best; s.Mode = 1;
            s.Path = PathTo(bp.X, bp.Y) ?? new List<Point>(); s.PathI = 0;
            return true;
        }

        IEnumerable<Point> Around(Obj o)
        {
            for (int x = o.X; x < o.X + o.W; x++)
            {
                if (InGrid(x, o.Y - 1) && Walkable(x, o.Y - 1)) yield return new Point(x, o.Y - 1);
                if (InGrid(x, o.Y + o.H) && Walkable(x, o.Y + o.H)) yield return new Point(x, o.Y + o.H);
            }
            for (int y = o.Y; y < o.Y + o.H; y++)
            {
                if (InGrid(o.X - 1, y) && Walkable(o.X - 1, y)) yield return new Point(o.X - 1, y);
                if (InGrid(o.X + o.W, y) && Walkable(o.X + o.W, y)) yield return new Point(o.X + o.W, y);
            }
        }

        bool FindLitter(Staff s)
        {
            if (litter.Count == 0)
            {
                foreach (var fl in floors)
                    if (fl.Index != s.Floor && fl.Litter.Count >= 3 && !StaffHeading(1, fl.Index) && StaffOn(1, fl.Index) == 0)
                        return TravelStaff(s, fl.Index);
                return false;
            }
            Flood(Clamp((int)s.X, 0, GW - 1), Clamp((int)s.Y, 0, GH - 1));
            int bd = int.MaxValue; Point bp = Point.Empty;
            for (int x = 0; x < GW; x++)
                for (int y = 0; y < GH; y++)
                {
                    if (litterGrid[x, y] == 0) continue;
                    int d = fdist[y * GW + x];
                    if (d < 0 || d >= bd) continue;
                    bool taken = false;
                    foreach (var o in staff) if (o != s && o.HasLitter && o.Litter.X == x && o.Litter.Y == y) taken = true;
                    if (!taken) { bd = d; bp = new Point(x, y); }
                }
            if (bd == int.MaxValue) return false;
            s.HasLitter = true; s.Litter = bp; s.Mode = 1;
            s.Path = PathTo(bp.X, bp.Y) ?? new List<Point>(); s.PathI = 0;
            return true;
        }

        void FinishJob(Staff s)
        {
            if (s.Role == 0 && s.Job != null)
            {
                s.Job.Broken = false; s.Job.Tech = null;
                Float(s.Job.X + s.Job.W / 2f, s.Job.Y, "Opraveno", Pal.Green);
            }
            if (s.Role == 1 && s.HasLitter)
            {
                // koště zamete pole i jeho okolí
                int x = s.Litter.X, y = s.Litter.Y;
                litter.RemoveAll(p => Math.Abs((int)p.X - x) <= 1 && Math.Abs((int)p.Y - y) <= 1);
                for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) if (InGrid(x + i, y + j)) litterGrid[x + i, y + j] = 0;
            }
            s.Job = null; s.HasLitter = false; s.Mode = 0; s.Timer = .5f + (float)rng.NextDouble();
        }

        bool StaffHeading(int role, int floor) { foreach (var o in staff) if (o.Role == role && o.TravelTo == floor) return true; return false; }
        int StaffOn(int role, int floor) { int n = 0; foreach (var o in staff) if (o.Role == role && o.Floor == floor && o.TravelTo < 0) n++; return n; }

        bool TravelStaff(Staff s, int floor)
        {
            Flood(Clamp((int)s.X, 0, GW - 1), Clamp((int)s.Y, 0, GH - 1));
            if (!GoEscalator(s, floor)) return false;
            s.Mode = 1;
            return true;
        }

        void StaffWander(Staff s)
        {
            // ochranka občas přejde na jiné patro
            if (s.Role == 2 && floors.Count > 1 && rng.NextDouble() < .25 && TravelStaff(s, rng.Next(floors.Count))) return;
            Flood(Clamp((int)s.X, 0, GW - 1), Clamp((int)s.Y, 0, GH - 1));
            var own = OwnLevels[ownLevel];
            for (int k = 0; k < 30; k++)
            {
                int x = own.X + rng.Next(own.Width), y = own.Y + rng.Next(own.Height);
                int d = fdist[y * GW + x];
                if (d >= 2 && d <= 9) { s.Path = PathTo(x, y); s.PathI = 0; s.Mode = 1; return; }
            }
            s.Timer = 2;
        }

        // ---------- mřížka a cesty ----------

        static bool InGrid(int x, int y) { return x >= 0 && y >= 0 && x < GW && y < GH; }
        bool InOwn(int x, int y) { return OwnLevels[ownLevel].Contains(x, y); }
        bool Walkable(int x, int y) { return InGrid(x, y) && InOwn(x, y) && occ[x, y] == null; }
        static bool IsEscalator(int x, int y) { return (x == 16 || x == 17) && y >= 16; }
        bool IsEntrance(int x, int y) { return (CF.Index == 0 && (x == 13 || x == 14) && y >= 16) || IsEscalator(x, y); }
        Point Origin { get { return CF.Index == 0 ? new Point(13, 17) : new Point(16, 17); } }

        void Flood(int sx, int sy)
        {
            for (int i = 0; i < fdist.Length; i++) fdist[i] = -1;
            int head = 0, tail = 0, s = sy * GW + sx;
            fdist[s] = 0; fprev[s] = -1; fqueue[tail++] = s;
            while (head < tail)
            {
                int c = fqueue[head++], cx = c % GW, cy = c / GW;
                for (int k = 0; k < 4; k++)
                {
                    int nx = cx + (k == 0 ? 1 : k == 1 ? -1 : 0), ny = cy + (k == 2 ? 1 : k == 3 ? -1 : 0);
                    if (!InGrid(nx, ny)) continue;
                    int n = ny * GW + nx;
                    if (fdist[n] >= 0 || !Walkable(nx, ny)) continue;
                    fdist[n] = fdist[c] + 1; fprev[n] = c; fqueue[tail++] = n;
                }
            }
        }

        List<Point> PathTo(int x, int y)
        {
            int c = y * GW + x;
            if (!InGrid(x, y) || fdist[c] < 0) return null;
            var list = new List<Point>();
            while (c >= 0 && fdist[c] > 0) { list.Add(new Point(c % GW, c / GW)); c = fprev[c]; }
            list.Reverse();
            return list;
        }

        // 0 jde, 1 došel, 2 cesta je zablokovaná
        int StepPath(Agent a, float speed, float dt)
        {
            if (a.Path == null || a.PathI >= a.Path.Count) return 1;
            var p = a.Path[a.PathI];
            if (!Walkable(p.X, p.Y)) return 2;
            float tx = p.X + .5f, ty = p.Y + .5f, dx = tx - a.X, dy = ty - a.Y;
            float d = (float)Math.Sqrt(dx * dx + dy * dy), step = speed * dt;
            a.Walk += dt * 12;
            if (d <= step)
            {
                a.X = tx; a.Y = ty; a.PathI++;
                return a.PathI >= a.Path.Count ? 1 : 0;
            }
            a.FaceX = dx / d; a.FaceY = dy / d;
            a.X += a.FaceX * step; a.Y += a.FaceY * step;
            return 0;
        }

        // ---------- stavění ----------

        // rozměry půdorysu po otočení
        static Size Dims(ObjType t, int dir) { return dir % 2 == 1 ? new Size(t.H, t.W) : new Size(t.W, t.H); }

        // místa pro hosty; stejné mapování jako otočení grafiky
        static Point[] SeatsFor(ObjType t, int x, int y, int dir)
        {
            var r = new Point[t.Seats.Length];
            for (int i = 0; i < r.Length; i++)
            {
                int sx = t.Seats[i].X, sy = t.Seats[i].Y;
                Point p;
                switch (dir)
                {
                    case 1: p = new Point(t.H - 1 - sy, sx); break;
                    case 2: p = t.Mirror ? new Point(sx, t.H - 1 - sy) : new Point(t.W - 1 - sx, t.H - 1 - sy); break;
                    case 3: p = new Point(sy, t.W - 1 - sx); break;
                    default: p = new Point(sx, sy); break;
                }
                r[i] = new Point(x + p.X, y + p.Y);
            }
            return r;
        }

        void Fill(int x, int y, Size d, Obj o)
        {
            for (int i = 0; i < d.Width; i++) for (int j = 0; j < d.Height; j++) occ[x + i, y + j] = o;
        }

        string Validate(ObjType t, int x, int y, int dir)
        {
            var d = Dims(t, dir);
            for (int i = 0; i < d.Width; i++)
                for (int j = 0; j < d.Height; j++)
                {
                    int fx = x + i, fy = y + j;
                    if (!InGrid(fx, fy) || !InOwn(fx, fy)) return "Mimo herní sál";
                    if (occ[fx, fy] != null) return "Místo je obsazené";
                    if (IsEntrance(fx, fy)) return "Vchod musí zůstat volný";
                }
            var seats = SeatsFor(t, x, y, dir);
            Fill(x, y, d, new Obj { T = t, X = x, Y = y, W = d.Width, H = d.Height });
            string err = null;
            Flood(Origin.X, Origin.Y);
            if (seats.Length > 0 && !AnyReachable(seats)) err = "K tomuhle místu nevede cesta";
            if (err == null && fdist[17 * GW + 16] < 0) err = "Zablokoval bys eskalátor";
            if (err == null)
                foreach (var o in objs)
                    if (o.Seats.Length > 0 && !AnyReachable(o.Seats)) { err = "Zablokoval bys přístup: " + o.T.Name; break; }
            Fill(x, y, d, null);
            return err;
        }

        bool AnyReachable(Point[] seats)
        {
            foreach (var s in seats)
                if (InGrid(s.X, s.Y) && Walkable(s.X, s.Y) && fdist[s.Y * GW + s.X] >= 0) return true;
            return false;
        }

        int CostOf(ObjType t) { return discountMin > 0 && t.Kind == ObjKind.Slot ? t.Cost * 7 / 10 : t.Cost; }

        string CanBuild(ObjType t, int x, int y, int dir)
        {
            if (carry != null) return Validate(t, x, y, dir);
            if (t.Stars > maxStars) return "Odemkne se od " + t.Stars + " " + StarWord(t.Stars);
            string e = Validate(t, x, y, dir);
            if (e != null) return e;
            if (money < CostOf(t)) return "Nemáš dost peněz";
            return null;
        }

        Obj Place(ObjType t, int x, int y, int dir, bool free)
        {
            var o = new Obj { T = t, X = x, Y = y, Dir = t.Rot ? dir : 0, Floor = CF.Index };
            o.Users = new Guest[t.Seats.Length];
            o.Spin = new float[Math.Max(1, t.Seats.Length)];
            o.Reels = new int[3 * Math.Max(1, t.Seats.Length)];
            for (int i = 0; i < o.Reels.Length; i++) o.Reels[i] = rng.Next(5);
            o.Anim = (float)rng.NextDouble() * 10;
            SetPos(o, x, y, o.Dir);
            objs.Add(o);
            if (!free) { int c = CostOf(t); money -= c; today.Build += c; }
            RecomputeMaps();
            AfterBuild();
            return o;
        }

        void SetPos(Obj o, int x, int y, int dir)
        {
            var d = Dims(o.T, dir);
            o.X = x; o.Y = y; o.Dir = dir; o.W = d.Width; o.H = d.Height;
            o.Seats = SeatsFor(o.T, x, y, dir);
            Fill(x, y, d, o);
        }

        void AfterBuild()
        {
            var agents = new List<Agent>();
            agents.AddRange(guests); agents.AddRange(staff);
            foreach (var a in agents)
            {
                if (a.Floor != CF.Index) continue;
                int tx = Clamp((int)a.X, 0, GW - 1), ty = Clamp((int)a.Y, 0, GH - 1);
                if (Walkable(tx, ty)) continue;
                Flood(tx, ty);
                int best = -1, bd = int.MaxValue;
                for (int i = 0; i < fdist.Length; i++) if (fdist[i] > 0 && fdist[i] < bd) { bd = fdist[i]; best = i; }
                if (best < 0) { best = Origin.Y * GW + Origin.X; }
                a.X = best % GW + .5f; a.Y = best / GW + .5f; a.Path = null;
                var g = a as Guest;
                if (g != null) { if (g.State == GS.Leave) GoExit(g); else { Release(g); Decide(g); } }
                var s = a as Staff;
                if (s != null) ReleaseJob(s);
            }
            foreach (var o in objs)
                for (int i = 0; i < o.Seats.Length; i++)
                {
                    var u = o.Users[i];
                    if (u != null && !Walkable(o.Seats[i].X, o.Seats[i].Y)) { Release(u); Decide(u); }
                }
        }

        // vyjme objekt z mřížky (prodej, přesun, otočení)
        void Detach(Obj o)
        {
            Fill(o.X, o.Y, new Size(o.W, o.H), null);
            objs.Remove(o);
            foreach (var s in staff) if (s.Job == o) ReleaseJob(s);
            foreach (var g in guests) if (g.Target == o) { Release(g); if (g.State != GS.Leave) Decide(g); }
        }

        void Sell(Obj o)
        {
            int refund = o.T.Cost / 2;
            money += refund; today.Build -= refund;
            Detach(o);
            if (sel == o) sel = null;
            RecomputeMaps();
        }

        // otočí o 90° po směru hodinek; zkusí stejný roh i stejný střed
        bool Rotate(Obj o)
        {
            if (!o.T.Rot) return false;
            int ox0 = o.X, oy0 = o.Y, od = o.Dir;
            float cx = o.X + o.W / 2f, cy = o.Y + o.H / 2f;
            Detach(o);
            string err = null;
            for (int k = 1; k <= 3; k++)
            {
                int nd = (od + k) % 4;
                var d = Dims(o.T, nd);
                var tries = new[] { new Point(ox0, oy0), new Point((int)Math.Round(cx - d.Width / 2f), (int)Math.Round(cy - d.Height / 2f)) };
                foreach (var p in tries)
                {
                    string e = Validate(o.T, p.X, p.Y, nd);
                    if (e == null)
                    {
                        SetPos(o, p.X, p.Y, nd); objs.Add(o);
                        RecomputeMaps(); AfterBuild();
                        return true;
                    }
                    if (err == null) err = e;
                }
            }
            SetPos(o, ox0, oy0, od); objs.Add(o);
            RecomputeMaps();
            Note("Nejde otočit: " + err, Pal.Red);
            flashErr = "Nejde otočit: " + err; flashErrT = 2;
            return false;
        }

        // ---------- přesouvání ----------

        Obj carry;
        int carryX, carryY, carryDir;

        void PickUp(Obj o)
        {
            if (carry != null) CancelCarry();
            Detach(o);
            RecomputeMaps();
            carry = o; carryX = o.X; carryY = o.Y; carryDir = o.Dir;
            tool = o.T; toolDir = o.Dir; sellTool = false; moveTool = false;
            ClearSelection();
            Sfx(sClick);
        }

        bool DropAt(int x, int y, int dir)
        {
            if (carry == null) return false;
            string e = Validate(carry.T, x, y, dir);
            if (e != null) { flashErr = e; flashErrT = 2; Sfx(sErr); return false; }
            var o = carry;
            carry = null; tool = null;
            o.Users = new Guest[o.T.Seats.Length];
            SetPos(o, x, y, dir);
            objs.Add(o);
            RecomputeMaps(); AfterBuild();
            sel = o;
            Dust(o.X, o.Y, o.W, o.H);
            Sfx(sPlace);
            return true;
        }

        void CancelCarry()
        {
            if (carry == null) return;
            var o = carry;
            carry = null; tool = null;
            o.Users = new Guest[o.T.Seats.Length];
            SetPos(o, carryX, carryY, carryDir);
            objs.Add(o);
            RecomputeMaps(); AfterBuild();
        }
        void Expand()
        {
            if (ownLevel >= 3) return;
            int cost = OwnCost[ownLevel + 1];
            if (money < cost) { Note("Na rozšíření sálu potřebuješ " + FormatKc(cost) + ".", Pal.Red); Sfx(sErr); return; }
            money -= cost; today.Build += cost; ownLevel++;
            floorDirty = true;
            RecomputeMaps();
            var r = OwnLevels[ownLevel];
            Note("Sál rozšířen na " + r.Width + " × " + r.Height + " polí.", Pal.Cyan);
            Sfx(sGoal);
        }

        void StartCampaign()
        {
            if (campaignMin > 0) return;
            if (money < 8000) { Sfx(sErr); return; }
            money -= 8000; today.Events += 8000; campaignMin = 1440;
            Note("Reklamní kampaň běží: 24 hodin přijde víc hostů.", Pal.Cyan);
            Sfx(sPlace);
        }

        void BuyUp(Upgrade u)
        {
            if (u.Owned || u.Stars > maxStars) return;
            if (money < u.Cost) { Sfx(sErr); return; }
            money -= u.Cost; today.Build += u.Cost; u.Owned = true;
            RecomputeMaps();
            Note("Vylepšení koupeno: " + u.Name, Pal.Cyan);
            Sfx(sGoal);
        }

        void RecomputeMaps()
        {
            attractTotal = 2; gameSeats = 0; upkeepSum = 0;
            bool clover = Has("clover");
            foreach (var fl in floors)
            {
                fl.Decor = new float[GW, GH]; fl.BinNear = new bool[GW, GH];
            }
            foreach (var o in AllObjs())
            {
                var fl = floors[o.Floor];
                upkeepSum += o.T.Upkeep;
                float a = o.T.Attract;
                if (clover && o.T.Kind == ObjKind.Slot) a *= 1.2f;
                attractTotal += a;
                if (o.T.IsGame) gameSeats += o.Seats.Length;
                if (o.T.Kind != ObjKind.Decor && o.T.Kind != ObjKind.Bin) continue;
                float cx = o.X + o.W / 2f, cy = o.Y + o.H / 2f;
                for (int x = 0; x < GW; x++)
                    for (int y = 0; y < GH; y++)
                    {
                        float dx = x + .5f - cx, dy = y + .5f - cy, d = (float)Math.Sqrt(dx * dx + dy * dy);
                        if (d > 4.5f) continue;
                        if (o.T.Kind == ObjKind.Bin) fl.BinNear[x, y] = true;
                        else fl.Decor[x, y] += o.T.Attract * (1 - d / 5.5f);
                    }
            }
        }

        // ---------- pomocné ----------

        int CountKind(ObjKind k) { int n = 0; foreach (var o in AllObjs()) if (o.T.Kind == k) n++; return n; }
        int CountId(string id) { int n = 0; foreach (var o in AllObjs()) if (o.T.Id == id) n++; return n; }
        int StaffCount(int role) { int n = 0; foreach (var s in staff) if (s.Role == role) n++; return n; }
        int BrokenCount() { int n = 0; foreach (var o in AllObjs()) if (o.Broken) n++; return n; }

        static readonly int[] StarRating = { 0, 0, 45, 56, 66, 76 };

        int StarsNow() { return Math.Min(RatingStars(), PrestigeCap()); }

        int RatingStars()
        {
            if (leftCount < 8) return 1;
            int s = 1;
            while (s < 5 && rating >= StarRating[s + 1]) s++;
            return s;
        }

        int PrestigeCap()
        {
            int cap = 1;
            for (int s = 2; s <= 5; s++)
            {
                bool ok = true;
                foreach (var r in StarReqs(s, false)) if (!r.Value) ok = false;
                if (!ok) break;
                cap = s;
            }
            return cap;
        }

        float DecorSum() { float a = 0; foreach (var o in AllObjs()) if (o.T.Kind == ObjKind.Decor) a += o.T.Attract; return a; }

        int TableKinds()
        {
            int n = 0;
            foreach (var id in new[] { "blackjack", "roulette", "poker" }) if (CountId(id) > 0) n++;
            return n;
        }

        // požadavky na danou hvězdu; withRating přidá i spokojenost hostů
        List<KeyValuePair<string, bool>> StarReqs(int s, bool withRating)
        {
            var r = new List<KeyValuePair<string, bool>>();
            Action<string, bool> add = (t, ok) => r.Add(new KeyValuePair<string, bool>(t, ok));
            int[] seats = { 0, 0, 8, 18, 32, 50 };
            int[] deco = { 0, 0, 0, 10, 30, 60 };
            add("Místa u her: " + gameSeats + " / " + seats[s], gameSeats >= seats[s]);
            if (s == 2) { add("Bar", CountKind(ObjKind.Bar) > 0); add("Toalety", CountKind(ObjKind.Wc) > 0); }
            if (s == 3) { add("Aspoň jeden stůl", CountKind(ObjKind.Table) > 0); add("Bankomat", CountKind(ObjKind.Atm) > 0); }
            if (s == 4) { add("Dva různé druhy stolů", TableKinds() >= 2); add("Pohovka pro unavené hosty", CountKind(ObjKind.Sofa) > 0); }
            if (s == 5) { add("Jackpot Island", CountId("island") > 0); add("Socha APEX", CountId("statue") > 0); }
            if (deco[s] > 0) add("Dekorace: atraktivita " + (int)DecorSum() + " / " + deco[s], DecorSum() >= deco[s]);
            if (withRating)
                add("Spokojenost hostů: " + (leftCount < 8 ? "zatím málo hostů" : (int)rating + " %") + " / " + StarRating[s] + " %", leftCount >= 8 && rating >= StarRating[s]);
            return r;
        }

        float CasinoValue()
        {
            float v = money;
            foreach (var o in AllObjs()) v += o.T.Cost * .6f;
            foreach (var fl in floors)
            {
                for (int i = 1; i <= fl.Own; i++) v += OwnCost[i] * .8f;
                v += FloorCost[fl.Index] * .8f;
            }
            foreach (var u in ups) if (u.Owned) v += u.Cost * .5f;
            return v;
        }

        static string StarWord(int n) { return n == 1 ? "hvězdy" : "hvězd"; }
        static int Clamp(int v, int a, int b) { return v < a ? a : v > b ? b : v; }

        static readonly CultureInfo Cz = CultureInfo.GetCultureInfo("cs-CZ");
        static string FormatKc(float v) { return ((int)Math.Round(v)).ToString("N0", Cz) + " Kč"; }
        string TimeStr() { int m = (int)minutes; return (m / 60).ToString("00") + ":" + (m % 60).ToString("00"); }

        void Note(string text, Color c)
        {
            notes.Add(new Note { T = text, C = c, When = "D" + day + " " + TimeStr() });
            if (notes.Count > 60) notes.RemoveAt(0);
        }

        // ---------- ukládání ----------

        void Save(bool auto)
        {
            try
            {
                var ci = CultureInfo.InvariantCulture;
                var sb = new StringBuilder();
                sb.AppendLine("APEXKASINO 2");
                sb.AppendLine(string.Format(ci, "G {0} {1} {2} {3} {4} {5} {6} {7} {8} {9} {10} {11} {12}",
                    money, day, minutes, floors[0].Own, rating, leftCount, totalGuests, maxStars, goalIdx, pool, campaignMin, bestDayProfit, cheatsCaught));
                foreach (var fl in floors) sb.AppendLine("L " + fl.Index + " " + fl.Own);
                foreach (var o in AllObjs()) sb.AppendLine(string.Format(ci, "O {0} {1} {2} {3} {4} {5} {6}", o.T.Id, o.X, o.Y, o.Dir, o.Broken ? 1 : 0, o.IncomeTotal, o.Floor));
                if (carry != null) sb.AppendLine(string.Format(ci, "O {0} {1} {2} {3} {4} {5} {6}", carry.T.Id, carryX, carryY, carryDir, carry.Broken ? 1 : 0, carry.IncomeTotal, carry.Floor));
                sb.AppendLine(TeamSaveLine(ci));
                sb.AppendLine(string.Format(ci, "E {0} {1} {2} {3}", discountMin, vipBoostMin, sturdyMin, eventCooldown));
                foreach (var s in staff) sb.AppendLine("S " + s.Role);
                foreach (var u in ups) if (u.Owned) sb.AppendLine("U " + u.Id);
                foreach (var d in history) sb.AppendLine(StatsLine("D", d, ci));
                sb.AppendLine(StatsLine("T", today, ci));
                Directory.CreateDirectory(saveDir);
                File.WriteAllText(SavePath, sb.ToString(), Encoding.UTF8);
                if (!auto) Note("Hra uložena.", Pal.Muted);
            }
            catch (Exception ex) { Note("Uložení selhalo: " + ex.Message, Pal.Red); }
        }

        static string StatsLine(string tag, DayStats d, CultureInfo ci)
        {
            return string.Format(ci, "{0} {1} {2} {3} {4} {5} {6} {7} {8} {9} {10} {11}",
                tag, d.Day, d.Guests, d.Slots, d.Tables, d.Bar, d.Atm, d.Wages, d.Upkeep, d.Events, d.Build, d.Rewards);
        }

        static DayStats ParseStats(string[] p, CultureInfo ci)
        {
            Func<int, float> f = i => float.Parse(p[i], ci);
            return new DayStats
            {
                Day = int.Parse(p[1], ci), Guests = int.Parse(p[2], ci), Slots = f(3), Tables = f(4), Bar = f(5), Atm = f(6),
                Wages = f(7), Upkeep = f(8), Events = f(9), Build = f(10), Rewards = f(11)
            };
        }

        bool HasSave() { return File.Exists(SavePath); }

        bool LoadGame()
        {
            try
            {
                var lines = File.ReadAllLines(SavePath);
                if (lines.Length == 0 || !lines[0].StartsWith("APEXKASINO")) return false;
                var ci = CultureInfo.InvariantCulture;
                bool v1 = lines[0].Trim() == "APEXKASINO 1";
                NewGame(false);
                notes.Clear();
                foreach (var line in lines)
                {
                    var p = line.Split(' ');
                    switch (p[0])
                    {
                        case "G":
                            money = float.Parse(p[1], ci); day = int.Parse(p[2], ci); minutes = float.Parse(p[3], ci);
                            floors[0].Own = int.Parse(p[4], ci); rating = float.Parse(p[5], ci); leftCount = int.Parse(p[6], ci);
                            totalGuests = int.Parse(p[7], ci); maxStars = int.Parse(p[8], ci); goalIdx = int.Parse(p[9], ci);
                            pool = float.Parse(p[10], ci); campaignMin = float.Parse(p[11], ci); bestDayProfit = float.Parse(p[12], ci);
                            cheatsCaught = int.Parse(p[13], ci);
                            // verze 1 neměla cíle „vedení“ (index 9) a „1. patro“ (index 12)
                            if (v1) goalIdx = goalIdx < 9 ? goalIdx : goalIdx < 11 ? goalIdx + 1 : goalIdx + 2;
                            break;
                        case "L":
                            {
                                int idx = int.Parse(p[1], ci);
                                while (floors.Count <= idx) floors.Add(new Floor { Index = floors.Count });
                                floors[idx].Own = int.Parse(p[2], ci);
                                break;
                            }
                        case "M": TeamLoad(p, ci); break;
                        case "O":
                            {
                                var t = Catalog.Get(p[1]);
                                if (t == null) break;
                                int fl = p.Length > 7 ? int.Parse(p[7], ci) : 0;
                                if (fl >= floors.Count) break;
                                CF = floors[fl];
                                var o = Place(t, int.Parse(p[2], ci), int.Parse(p[3], ci), int.Parse(p[4], ci), true);
                                o.Broken = p[5] == "1"; o.IncomeTotal = float.Parse(p[6], ci);
                                break;
                            }
                        case "S": Hire(int.Parse(p[1], ci)); break;
                        case "E":
                            discountMin = float.Parse(p[1], ci); vipBoostMin = float.Parse(p[2], ci);
                            sturdyMin = float.Parse(p[3], ci); eventCooldown = float.Parse(p[4], ci);
                            break;
                        case "U": foreach (var u in ups) if (u.Id == p[1]) u.Owned = true; break;
                        case "D": history.Add(ParseStats(p, ci)); break;
                        case "T": today = ParseStats(p, ci); break;
                    }
                }
                CF = floors[0]; viewFloor = 0;
                RecomputeMaps();
                floorDirty = true;
                Note("Hra načtena – den " + day + ".", Pal.Muted);
                return true;
            }
            catch (Exception ex)
            {
                NewGame(false);
                Note("Načtení selhalo: " + ex.Message, Pal.Red);
                return false;
            }
        }
    }
}
