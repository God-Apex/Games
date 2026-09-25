using System;
using System.Collections.Generic;
using System.Drawing;

namespace ApexKasino
{
    class GameEvent
    {
        public string Title, Text;
        public string[] Options;
        public Action<int> Apply;
    }

    // náhodné události s volbou a jejich dočasné efekty
    partial class GameForm
    {
        GameEvent activeEvent;
        float eventCooldown = 600, discountMin, vipBoostMin, sturdyMin, partyT;
        int partyGuests;

        void ResetEvents()
        {
            activeEvent = null; eventCooldown = 600;
            discountMin = vipBoostMin = sturdyMin = 0; partyGuests = 0;
        }

        void UpdateEffects(float dt, float dmin)
        {
            eventCooldown = Math.Max(0, eventCooldown - dmin);
            discountMin = Math.Max(0, discountMin - dmin);
            vipBoostMin = Math.Max(0, vipBoostMin - dmin);
            sturdyMin = Math.Max(0, sturdyMin - dmin);
            if (partyGuests > 0)
            {
                partyT -= dt;
                if (partyT <= 0)
                {
                    partyT = .7f; partyGuests--;
                    var g = SpawnGuest();
                    g.Money = g.Budget = (float)Math.Round(g.Budget * 1.5f / 100) * 100;
                    g.Happy = 88;
                    Think(g, "Na zdraví APEXu!", 3);
                    Decide(g);
                }
            }
        }

        void MaybeEvent()
        {
            if (demo || activeEvent != null || eventCooldown > 0 || CountKind(ObjKind.Slot) < 4) return;
            int h = (int)(minutes / 60);
            if (h < 12 || rng.NextDouble() > .16) return;
            var list = new List<Func<GameEvent>>();
            list.Add(EvParty); list.Add(EvPower); list.Add(EvHygiene); list.Add(EvInfluencer);
            list.Add(EvDiscount); list.Add(EvNeighbour); list.Add(EvCelebrity);
            if (CountKind(ObjKind.Table) > 0) list.Add(EvTournament);
            if (BrokenCount() > 0 || day > 3) list.Add(EvFactory);
            activeEvent = list[rng.Next(list.Count)]();
            eventCooldown = 1440 * .75f;
            if (mgr[3])
            {
                int ch = AutoChoice(activeEvent);
                var ev = activeEvent;
                TeamLog(3, ev.Title + " → " + ev.Options[Math.Min(ch, ev.Options.Length - 1)]);
                ChooseEvent(Math.Min(ch, ev.Options.Length - 1));
                return;
            }
            Sfx(sDay);
        }

        void ChooseEvent(int i)
        {
            var ev = activeEvent;
            activeEvent = null;
            if (ev != null && ev.Apply != null) ev.Apply(i);
        }

        void Pay(float v) { money -= v; today.Events += v; }

        GameEvent EvParty()
        {
            return new GameEvent
            {
                Title = "Firemní večírek APEX",
                Text = "Kolegové z Litvínovic slaví rekordní rok a chtějí dnešní večer strávit u tebe. Přijde asi 20 lidí s plnými peněženkami.",
                Options = new[] { "Uspořádat (5 000 Kč)", "Tentokrát ne" },
                Apply = i =>
                {
                    if (i != 0) return;
                    Pay(5000); partyGuests = 20;
                    Note("Firemní večírek APEX začíná!", Pal.Yellow);
                }
            };
        }

        GameEvent EvTournament()
        {
            return new GameEvent
            {
                Title = "Pokerový turnaj",
                Text = "Místní klub hledá kasino pro víkendový turnaj. Na 24 hodin by chodilo mnohem víc VIP hostů.",
                Options = new[] { "Pořádat (12 000 Kč)", "Nemáme zájem" },
                Apply = i =>
                {
                    if (i != 0) return;
                    Pay(12000); vipBoostMin = 1440;
                    Note("Turnaj běží – chodí víc VIP hostů.", Pal.Gold);
                }
            };
        }

        GameEvent EvPower()
        {
            return new GameEvent
            {
                Title = "Výpadek proudu",
                Text = "V celé čtvrti vypadl proud. Záložní agregát stroje ochrání, jinak se po restartu několik automatů porouchá.",
                Options = new[] { "Zapnout agregát (6 000 Kč)", "Riskovat" },
                Apply = i =>
                {
                    if (i == 0) { Pay(6000); Note("Agregát naskočil, všechno běží.", Pal.Green); return; }
                    int n = 0;
                    var games = objs.FindAll(o => o.T.IsGame && !o.Broken);
                    while (n < 3 && games.Count > 0)
                    {
                        var o = games[rng.Next(games.Count)];
                        games.Remove(o); o.Broken = true; n++;
                    }
                    Note("Po výpadku se porouchalo strojů: " + n + ".", Pal.Red);
                    Sfx(sBreak);
                }
            };
        }

        GameEvent EvHygiene()
        {
            int lit = LitterTotal();
            bool dirty = lit > 10;
            return new GameEvent
            {
                Title = "Hygienická kontrola",
                Text = dirty
                    ? "Inspektor našel na zemi " + lit + " kusů odpadků. Za nepořádek je pokuta 8 000 Kč."
                    : "Inspektor prošel celý sál a nenašel nic, co by vytkl. Pochvala se rychle rozkřikne.",
                Options = new[] { dirty ? "Zaplatit pokutu" : "Děkujeme" },
                Apply = i =>
                {
                    if (dirty) { Pay(8000); Note("Pokuta za nepořádek: 8 000 Kč. Najmi uklízeče.", Pal.Red); }
                    else { rating = Math.Min(100, rating + 3); Note("Kontrola dopadla výborně, hodnocení roste.", Pal.Green); }
                }
            };
        }

        GameEvent EvInfluencer()
        {
            return new GameEvent
            {
                Title = "Influencerka chce natáčet",
                Text = "Známá influencerka by u tebe natočila video. Zadarmo, ale co v něm řekne, záleží na tom, jak se jí u tebe bude líbit.",
                Options = new[] { "Povolit natáčení", "Odmítnout" },
                Apply = i =>
                {
                    if (i != 0) return;
                    if (rating >= 60 || rng.NextDouble() < .5)
                    {
                        campaignMin = Math.Max(campaignMin, 720);
                        Note("Video má tisíce zhlédnutí – 12 hodin chodí víc hostů.", Pal.Green);
                    }
                    else
                    {
                        rating = Math.Max(0, rating - 5);
                        Note("Video nebylo lichotivé. Hodnocení kleslo.", Pal.Red);
                    }
                }
            };
        }

        GameEvent EvDiscount()
        {
            return new GameEvent
            {
                Title = "Nabídka od APEX",
                Text = "Obchodní oddělení APEX nabízí na 24 hodin slevu 30 % na všechny automaty. Ideální chvíle rozšířit herní plochu.",
                Options = new[] { "Objednat se slevou", "Teď nepotřebuju" },
                Apply = i =>
                {
                    if (i != 0) return;
                    discountMin = 1440;
                    Note("Sleva 30 % na automaty platí 24 hodin.", Pal.Cyan);
                }
            };
        }

        GameEvent EvNeighbour()
        {
            return new GameEvent
            {
                Title = "Stížnost souseda",
                Text = "Soused si stěžuje na hluk z parkoviště. Chce odškodné, jinak prý napíše špatnou recenzi.",
                Options = new[] { "Zaplatit 3 000 Kč", "Ignorovat" },
                Apply = i =>
                {
                    if (i == 0) { Pay(3000); Note("Soused je spokojený.", Pal.Muted); return; }
                    if (rng.NextDouble() < .5) { rating = Math.Max(0, rating - 4); Note("Soused napsal zlou recenzi. Hodnocení kleslo.", Pal.Red); }
                    else Note("Soused to nakonec pustil z hlavy.", Pal.Muted);
                }
            };
        }

        GameEvent EvCelebrity()
        {
            return new GameEvent
            {
                Title = "Slavný host",
                Text = "Na cestě je známý podnikatel, který rád utrácí. VIP servis ho potěší – a potěšený host utrácí víc.",
                Options = new[] { "Připravit VIP servis (4 000 Kč)", "Nic zvláštního" },
                Apply = i =>
                {
                    var g = SpawnGuest();
                    g.Vip = true; g.Shirt = Color.FromArgb(30, 30, 36);
                    g.Money = g.Budget = i == 0 ? 150000 : 60000;
                    g.Happy = i == 0 ? 95 : 60;
                    if (i == 0) Pay(4000);
                    Think(g, i == 0 ? "Tady to umí. Jdu hrát!" : "Tak uvidíme…", i == 0 ? 3 : -1);
                    Decide(g);
                    selGuest = g; sel = null; selStaff = null;
                    Note(g.Name + " právě přišel do kasina.", Pal.Gold);
                }
            };
        }

        GameEvent EvFactory()
        {
            return new GameEvent
            {
                Title = "Návštěva z výroby",
                Text = "Technici APEX z Litvínovic jsou v okolí. Zkontrolují všechny stroje a den se nic nepokazí.",
                Options = new[] { "Skvělé, díky!" },
                Apply = i =>
                {
                    foreach (var o in objs) if (o.Broken) { o.Broken = false; if (o.Tech != null) ReleaseJob(o.Tech); }
                    sturdyMin = 1440;
                    Note("Technici APEX zkontrolovali stroje – 24 hodin bez poruch.", Pal.Green);
                }
            };
        }

        // aktivní efekty pro zobrazení
        List<KeyValuePair<string, Color>> ActiveEffects()
        {
            var r = new List<KeyValuePair<string, Color>>();
            if (campaignMin > 0) r.Add(new KeyValuePair<string, Color>("Kampaň " + (int)Math.Ceiling(campaignMin / 60) + " h", Pal.Cyan));
            if (discountMin > 0) r.Add(new KeyValuePair<string, Color>("Sleva 30 % " + (int)Math.Ceiling(discountMin / 60) + " h", Pal.Yellow));
            if (vipBoostMin > 0) r.Add(new KeyValuePair<string, Color>("Turnaj · VIP " + (int)Math.Ceiling(vipBoostMin / 60) + " h", Pal.Gold));
            if (sturdyMin > 0) r.Add(new KeyValuePair<string, Color>("Bez poruch " + (int)Math.Ceiling(sturdyMin / 60) + " h", Pal.Green));
            if (partyGuests > 0) r.Add(new KeyValuePair<string, Color>("Večírek APEX", Pal.Cream));
            return r;
        }

        void DrawEvent(Graphics g)
        {
            var ev = activeEvent;
            g.FillRectangle(B(150, Pal.Night), MX, MY, GW * TS, GH * TS);
            var r = new RectangleF(MX + 448 - 250, MY + 150, 500, 250);
            FillRound(g, B(250, Pal.Panel), r, 14);
            DrawRound(g, P(Pal.Yellow, 2), r, 14);
            DrawPyramid(g, r.X + 34, r.Y + 20, 34, 27);
            Txt(g, "UDÁLOST", F(10, true), Pal.Yellow, r.X + 62, r.Y + 18);
            Txt(g, ev.Title, F(20, true), Color.White, r.X + 62, r.Y + 30);
            TxtWrap(g, ev.Text, F(13, false), Pal.Text, new RectangleF(r.X + 26, r.Y + 76, r.Width - 52, 100));
            float bw = ev.Options.Length == 1 ? 240 : 220;
            float total = ev.Options.Length * bw + (ev.Options.Length - 1) * 12;
            for (int i = 0; i < ev.Options.Length; i++)
            {
                int k = i;
                Button(g, new RectangleF(r.X + r.Width / 2 - total / 2 + i * (bw + 12), r.Bottom - 60, bw, 40), ev.Options[i], () => ChooseEvent(k), i == 0 ? 1 : 0, true);
            }
            TxtC(g, "hra stojí, dokud se nerozhodneš", F(9.5f, false), Pal.Dim, r.X + r.Width / 2, r.Bottom - 10);
        }
    }
}
