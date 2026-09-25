using System;
using System.Collections.Generic;
using System.Drawing;

namespace ApexKasino
{
    enum ObjKind { Slot, Table, Bar, Wc, Atm, Sofa, Decor, Bin }
    enum Cat { Automaty, Stoly, Sluzby, Dekorace }
    enum GS { Walk, Use, Leave }

    class ObjType
    {
        public string Id, Name, Desc;
        public Cat Cat;
        public ObjKind Kind;
        public int W = 1, H = 1, Cost, Upkeep, Stars, Attract, Price;
        public float Bet, Edge, Interval = 1.3f, Break, UseTime = 4;
        public Point[] Seats = new Point[0];
        public bool Rot, Mirror;   // Mirror: grafika umí zrcadlení (180° bez převráceného textu)

        public bool IsGame { get { return Kind == ObjKind.Slot || Kind == ObjKind.Table; } }
        public bool Breaks { get { return IsGame; } }
    }

    static class Catalog
    {
        public static readonly List<ObjType> All = new List<ObjType>();

        static ObjType Add(string id, string name, Cat cat, ObjKind k, int w, int h, int cost, int upkeep, int attract, int stars, string desc)
        {
            var t = new ObjType { Id = id, Name = name, Cat = cat, Kind = k, W = w, H = h, Cost = cost, Upkeep = upkeep, Attract = attract, Stars = stars, Desc = desc };
            All.Add(t);
            return t;
        }

        static Point[] P(params int[] xy)
        {
            var r = new Point[xy.Length / 2];
            for (int i = 0; i < r.Length; i++) r[i] = new Point(xy[2 * i], xy[2 * i + 1]);
            return r;
        }

        static Catalog()
        {
            ObjType t;
            // automaty
            t = Add("retro", "APEX Retro 7", Cat.Automaty, ObjKind.Slot, 1, 1, 2000, 100, 1, 0,
                "Levný automat s nízkou sázkou pro opatrné hráče. Chromovaná klasika.");
            t.Bet = 50; t.Edge = .16f; t.Break = .007f; t.Seats = P(0, 1); t.Rot = t.Mirror = true;

            t = Add("classic", "APEX Classic", Cat.Automaty, ObjKind.Slot, 1, 1, 3500, 150, 1, 0,
                "Klasický automat. Levný a spolehlivý základ každé herny.");
            t.Bet = 100; t.Edge = .15f; t.Break = .006f; t.Seats = P(0, 1); t.Rot = t.Mirror = true;

            t = Add("clover", "Lucky Clover", Cat.Automaty, ObjKind.Slot, 1, 1, 6500, 200, 2, 1,
                "Zelený automat se čtyřlístkem. Hráči věří, že nosí štěstí.");
            t.Bet = 150; t.Edge = .145f; t.Break = .005f; t.Seats = P(0, 1); t.Rot = t.Mirror = true;

            t = Add("pyramid", "APEX Pyramid", Cat.Automaty, ObjKind.Slot, 1, 1, 8000, 250, 3, 2,
                "Prémiová skříň s pyramidou na topperu. Láká bohatší hráče.");
            t.Bet = 200; t.Edge = .14f; t.Break = .005f; t.Seats = P(0, 1); t.Rot = t.Mirror = true;

            t = Add("station", "Player Station", Cat.Automaty, ObjKind.Slot, 2, 1, 14000, 400, 4, 2,
                "Dvoumístná stanice se dvěma velkými displeji.");
            t.Bet = 150; t.Edge = .14f; t.Interval = 1.2f; t.Break = .005f; t.Seats = P(0, 1, 1, 1); t.Rot = t.Mirror = true;

            t = Add("multi", "Multi-Game Bank", Cat.Automaty, ObjKind.Slot, 3, 1, 18000, 550, 5, 2,
                "Řada tří propojených automatů se společnou hlavou. Spousta her na malém místě.");
            t.Bet = 120; t.Edge = .14f; t.Interval = 1.2f; t.Break = .005f; t.Seats = P(0, 1, 1, 1, 2, 1); t.Rot = t.Mirror = true;

            t = Add("diamond", "Diamond Deluxe", Cat.Automaty, ObjKind.Slot, 1, 1, 16000, 400, 5, 3,
                "Fialová prémiová skříň s diamantem. Vysoké sázky, vysoké výhry.");
            t.Bet = 500; t.Edge = .13f; t.Break = .004f; t.Seats = P(0, 1); t.Rot = t.Mirror = true;

            t = Add("wheel", "Kolo štěstí", Cat.Automaty, ObjKind.Slot, 2, 1, 26000, 700, 8, 3,
                "Dvoumístný automat s obřím kolem štěstí nahoře. Když se točí, dívá se celý sál.");
            t.Bet = 250; t.Edge = .135f; t.Interval = 1.4f; t.Break = .004f; t.Seats = P(0, 1, 1, 1); t.Rot = t.Mirror = true;

            t = Add("island", "Jackpot Island", Cat.Automaty, ObjKind.Slot, 2, 2, 48000, 1200, 12, 3,
                "Ostrov čtyř automatů se společným jackpotem uprostřed. Magnet na hosty.");
            t.Bet = 300; t.Edge = .13f; t.Break = .004f; t.Seats = P(0, -1, 1, -1, 0, 2, 1, 2); t.Rot = true;

            t = Add("tower", "Mega Tower VIP", Cat.Automaty, ObjKind.Slot, 1, 1, 32000, 800, 8, 4,
                "Černozlatá věž pro VIP hráče. Sázka 1 000 Kč za točku.");
            t.Bet = 1000; t.Edge = .12f; t.Break = .003f; t.Seats = P(0, 1); t.Rot = t.Mirror = true;

            // stoly
            t = Add("blackjack", "Blackjack", Cat.Stoly, ObjKind.Table, 3, 2, 22000, 1500, 5, 1,
                "Karetní stůl pro tři hráče. Mzda krupiéra je v ceně údržby.");
            t.Bet = 400; t.Edge = .06f; t.Interval = 3f; t.Break = .0015f; t.Seats = P(0, 2, 1, 2, 2, 2); t.Rot = true;

            t = Add("roulette", "Ruleta", Cat.Stoly, ObjKind.Table, 3, 2, 30000, 1800, 7, 2,
                "Ruleta pro šest hráčů. Symbol každého pořádného kasina.");
            t.Bet = 500; t.Edge = .054f; t.Interval = 4f; t.Break = .0015f; t.Seats = P(0, -1, 1, -1, 2, -1, 0, 2, 1, 2, 2, 2); t.Rot = true;

            t = Add("poker", "Poker", Cat.Stoly, ObjKind.Table, 3, 2, 55000, 2200, 9, 4,
                "Pokerový stůl pro šest hráčů. Sedají k němu ti nejbohatší hosté.");
            t.Bet = 800; t.Edge = .05f; t.Interval = 5f; t.Break = .0015f; t.Seats = P(0, -1, 1, -1, 2, -1, 0, 2, 1, 2, 2, 2); t.Rot = true;

            // služby
            t = Add("bar", "Bar", Cat.Sluzby, ObjKind.Bar, 3, 1, 12000, 900, 2, 0,
                "Hosté tu uhasí žízeň. Drink stojí 150 Kč.");
            t.Price = 150; t.UseTime = 4; t.Seats = P(0, 1, 1, 1, 2, 1); t.Rot = t.Mirror = true;

            t = Add("wc", "Toalety", Cat.Sluzby, ObjKind.Wc, 2, 2, 7000, 300, 0, 0,
                "Bez toalet hosté brzy naštvaně odcházejí.");
            t.UseTime = 4; t.Seats = P(0, 2, 1, 2); t.Rot = true;

            t = Add("atm", "Bankomat", Cat.Sluzby, ObjKind.Atm, 1, 1, 5000, 100, 0, 0,
                "Hosté bez hotovosti si vyberou peníze a hrají dál. Poplatek 120 Kč.");
            t.Price = 120; t.UseTime = 3; t.Seats = P(0, 1); t.Rot = t.Mirror = true;

            t = Add("sofa", "Pohovka", Cat.Sluzby, ObjKind.Sofa, 2, 1, 4500, 80, 1, 0,
                "Unavení hosté si tu odpočinou a zůstanou déle.");
            t.UseTime = 8; t.Seats = P(0, 1, 1, 1); t.Rot = t.Mirror = true;

            t = Add("bin", "Koš", Cat.Sluzby, ObjKind.Bin, 1, 1, 600, 20, 0, 0,
                "Hosté v okruhu 4 polí odhazují mnohem méně odpadků.");

            // dekorace
            Add("plant", "Květina", Cat.Dekorace, ObjKind.Decor, 1, 1, 800, 10, 2, 0,
                "Trocha zeleně. Zvedne náladu hostům v okolí.");
            Add("palm", "Palma", Cat.Dekorace, ObjKind.Decor, 1, 1, 1800, 20, 3, 0,
                "Velká palma v květináči. Dovolenková atmosféra.");
            t = Add("led", "LED panel XXL", Cat.Dekorace, ObjKind.Decor, 2, 1, 9000, 120, 6, 1,
                "Velký LED displej s běžícím textem a výší jackpotu.");
            t.Rot = true;
            Add("fountain", "Fontána", Cat.Dekorace, ObjKind.Decor, 2, 2, 14000, 200, 9, 2,
                "Fontána uprostřed sálu. Hosté u ní rádi postávají.");
            Add("statue", "Socha APEX", Cat.Dekorace, ObjKind.Decor, 2, 2, 26000, 150, 14, 3,
                "Zlatá pyramida APEX na podstavci. Hosté se s ní fotí.");
        }

        public static ObjType Get(string id)
        {
            foreach (var t in All) if (t.Id == id) return t;
            return null;
        }
    }

    class Upgrade
    {
        public string Id, Name, Desc;
        public int Cost, Stars;
        public bool Owned;
    }

    // jedno patro kasina: vlastní mřížka, objekty a odpadky
    class Floor
    {
        public int Index, Own;
        public List<Obj> Objs = new List<Obj>();
        public Obj[,] Occ = new Obj[28, 18];
        public List<PointF> Litter = new List<PointF>();
        public int[,] LitterGrid = new int[28, 18];
        public float[,] Decor = new float[28, 18];
        public bool[,] BinNear = new bool[28, 18];
    }

    class Obj
    {
        public ObjType T;
        public int X, Y, Dir, W, H, Floor;   // Dir 0 dolů, 1 vlevo, 2 nahoru, 3 vpravo
        public bool Broken;
        public Staff Tech;
        public Guest[] Users;
        public Point[] Seats;
        public float[] Spin;
        public int[] Reels;
        public float Anim, IncomeToday, IncomeTotal;
        public int Plays;

        public bool Down { get { return Dir == 0; } }
        public bool Covers(int x, int y) { return x >= X && x < X + W && y >= Y && y < Y + H; }
        public int UserCount
        {
            get { int n = 0; foreach (var u in Users) if (u != null && u.State == GS.Use && u.Target == this) n++; return n; }
        }
        public bool InUse(int seat)
        {
            var u = Users[seat];
            return u != null && u.State == GS.Use && u.Target == this;
        }
    }

    class Agent
    {
        public float X, Y, FaceX, FaceY = 1, Walk;
        public List<Point> Path;
        public int PathI, Floor, TravelTo = -1;
        public string Name;
    }

    class Guest : Agent
    {
        public bool Vip, Gone, Hidden, UsedAtm, NoBar, NoWc;
        public Color Shirt, Skin, Hair;
        public float Money, Budget, Happy, Thirst, Bladder, Energy, Won, VisitT;
        public GS State;
        public Obj Target;
        public int Seat = -1, Plays, PlaysGoal, Waits, Icon = -1;
        public float Timer, PlayT, ThoughtT;
        public string Thought = "";
    }

    class Staff : Agent
    {
        public int Role, Mode;          // Mode: 0 volno, 1 cesta, 2 práce
        public Obj Job;
        public bool HasLitter;
        public Point Litter;
        public float Timer, SearchT;
    }

    class Particle { public float X, Y, VX, VY, Life, Size; public Color C; public bool Coin; }
    class FloatText { public float X, Y, Life; public string T; public Color C; }
    class Note { public string T, When; public Color C; }

    class DayStats
    {
        public int Day, Guests;
        public float Slots, Tables, Bar, Atm, Wages, Upkeep, Events, Build, Rewards;
        public float Income { get { return Slots + Tables + Bar + Atm; } }
        public float Expense { get { return Wages + Upkeep + Events; } }
        public float Operating { get { return Income - Expense; } }
    }

    class Goal
    {
        public string Text;
        public Func<bool> Done;
        public Func<string> Progress;
        public int Reward;
    }

    class Btn
    {
        public RectangleF R;
        public Action A;
    }
}
