# PLANETAI Node. Product

Working draft, 2 September 2026. Not a grant. Someone pays or it dies.

This is the business case in one market. What the node is for, in the programme's own words, is the lead and
"What it is for" of `docs/site/introduction.md` (planetai.fab.city/docs/introduction/); this document does not
restate it.

This document argues the case in one market, Bali, because that is where the first node runs and where the numbers
are real. The shape of the argument is portable: find a place with a measurement gap, an acute local decision, and a
fab lab within driving distance of the hardware. The numbers are not portable, and anyone reusing this for Santiago
or Delhi should replace them rather than translate them.

## The problem, stated by the people already measuring it

Bali Air Dispatch, run out of the same circle as this project (MDG is a listed collaborator), has been publishing
the island's PM2.5 record since April 2026. Their numbers: fifteen public sensors for 4.4 million residents and
5,780 km². At the one sensor with a two-year record, 100% of days since June exceeded the WHO 24-hour guideline.
The pattern is household waste burning: a 9am spike and a second climb after dark, island-wide. Every AirGradient
unit deployed in Bali in 2025 went silent within the year.

Two things follow. The island has a data-*visibility* problem that BAD is already solving. And it has a
data-*to-action* problem nobody is solving: a family in Kuta Selatan with a sensor in the living room still
doesn't know whether to open the window. And sensors die because nobody's job is to keep them alive.

That second problem is the product.

## What it is

A node is a small computer at a place: a home, a school, a clinic, a banjar office, a hotel: that reads the
sensors there, reads the public sensors around it, and sends the people at that address one plain message when
something should change: shut the windows, run the purifier, ventilate, the sensor's dead, here's your week.

Software is free and open. You can install it on a Mac mini you already own and a Smart Citizen Kit you already
have, tonight, for nothing. That's the top of the funnel and it should stay free forever.

The thing people pay for is the same thing that killed every AirGradient in Bali last year: **someone whose job
it is to keep the sensor alive and the alerts correct.**

## Who buys, in order

1. **Households and villas in the burn corridor** (Kuta Selatan, Canggu, Kerobokan, Ubud). They already buy IQAir monitors at $269 to look at a number. They'll pay for the number to *tell them what to do* and for someone to come when it stops.
2. **Schools and clinics.** Sensitive populations, a duty of care, a budget line for "health and safety." The indoor/outdoor differential is a decision aid for recess, ward ventilation, and sports.
3. **Hotels and restaurants.** Already IQAir's hospitality customers. The differential plus a nightly brief is a guest-facing asset and a staff-facing SOP.
4. **Banjar and desa.** The public-good tier. Dana Desa funds it; the village gets its own sensor on the BAD map and a WhatsApp alert to the kelian. Slowest sale, biggest story.

Not a target yet: Barcelona, Boston, Santiago. They come when a Bali node has stayed alive for a year.

## The offer (draft: price the service, not the box)

| tier | what | who pays | notes |
|---|---|---|---|
| **Open** | software + docs. Bring your own sensor and computer. | nobody | forever free. this is distribution, and it's how fab labs join. |
| **Node kit** | sensor + preconfigured mini-PC or Pi + printed enclosure + install + Telegram/WhatsApp setup | one-time | hardware at cost + install fee. SCK 2.3 via Seeed, the sensor the installer offers today; AirGradient ONE ($125–225, ships from Thailand in a week) once the `air-sensors` pack reads it. Enclosure printed at Fab Lab Bali. |
| **Kept alive** | monthly: alerts, monthly brief, remote monitoring, sensor swap when it dies, one site visit a year | monthly | this is the business. margin lives here. |
| **Community** | one district node aggregating a desa's or a school cluster's nodes, public map presence, quarterly report to the kelian / principal | annual, Dana Desa or CSR | v0.2+, needs the aggregator |

Don't publish prices until five pilots have run for ninety days and we know what a sensor swap actually costs
in Bali. Import duty, WiFi flakiness, and the drive to Ubud are the real cost of goods.

## Why Fab City is the right owner

Not because of the brand. Because of the three things the network already has that a startup would have to build:

- **Manufacturing.** Enclosures printed locally, on demand, in the climate they'll live in. The outdoor-sensor-enclosure work is already done. Nobody imports a box.
- **Installation and maintenance labour.** Fab Lab Bali today; every fab lab in the network tomorrow. The "kept alive" tier is only possible because there's a workshop within driving distance.
- **A curriculum.** Fab Academy 2027 can carry "install and operate a node" as a module. That's a trained installer pipeline, worldwide, at zero marginal cost.

Bali Air Dispatch is one observatory instance, for one island, built by people in our own circle. PLANETAI's observatory is the *layer*: the same read API at every node, aggregator and region, feeding planetai.fab.city and index.fab.city. BAD is a source we read, a pattern we learned from, and a map we should densify with hardware fab labs keep alive. Not a competitor, not the ceiling.

## Ninety days

- **Now → day 14.** Node #1 (Bayu 2) live on the Mac. Telegram alerts to Tomas. Tune `BAD_RADIUS_KM` until `refs ≥ 3`. First real alert observed and judged: was it right, was it useful, was it too often.
- **Day 14 → 45.** Five pilot addresses, all within 20 km, mix of household / school / villa. Each gets a kit and the Kept Alive service free for 90 days in exchange for a weekly two-line answer: *did you do anything because of an alert this week?* Join the BAD WhatsApp community and say what we're doing; it's the exact audience.
- **Day 45 → 90.** One sensor will die. Fixing it is the product test. Write down what it cost. By day 90: publish the pilot numbers (alerts sent, actions taken, uptime, cost per swap), set prices, open the Kept Alive tier to paying customers.
- **Success at 90:** five nodes alive, at least one documented case where someone changed behaviour because of a message, and a price a household will pay.

## What could kill it

- **Nobody acts on the alerts.** Then the differential isn't the service and we find out fast. Cheap to learn.
- **Maintenance costs more than the tier.** Then it's a nonprofit or it's dead. Pilots exist to price this.
- **WhatsApp.** Indonesians live there; Telegram is our stopgap. Meta Business approval for templated alerts is a slog. Budget the slog.
- **The engineer.** Someone has to own install.sh across a zoo of machines. If it's Tomas past day 30, the product is a hobby.
- **BAD's API changes or goes away.** We store what we pull; the node keeps working on its own sensors. And we should be contributing sensors to BAD, not only reading it: that's what makes us a good neighbour and a resilient one.

## Names

"PLANETAI" is the programme. The thing at the address needs a name a household will say out loud. Not decided;
goes through the Fab City brand rules when it is. Working name in code: `planetai-node`.
