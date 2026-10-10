# Three things node #1 can tell you
<!-- checked: v0.80.10 -->

Computed on 5 September 2026 from seven days of data: three indoor kits at one house in Kuta Selatan, an outdoor kit
a kilometre away, and the Copernicus model at the house.

## Is the air in my house my problem or the street's?

This week, the street's. Indoor PM2.5 tracked the outdoor kit at r = 0.55, and the house held back about 30% (indoor
mean 5.8 against outdoor 9.6). No hour had indoor more than 10 above outdoor. Two indoor kits agreed at r = 0.73; the
sensors can be trusted.

The `insight` pack's daily `agreement` rule states this. When the room turns worse than the street, the `air-quality`
pack's `inside_worse_ventilate` fires: open a window.

## When should I open the windows?

Around 15:00. The street was worst at 18:00 (12.6) and 06:00 (11.0), the evening and morning burning, and cleanest
mid-afternoon (7.5). Indoors peaked at 18:00 and 09:00, following the street with a lag. The model read a flat 11–14
all day and missed the rhythm.

The `rhythm` rule says this daily, in local time, ending with the hour to air the house. It needs a local outdoor
noise sensor, and without one it stays silent.

## Should I trust the satellite?

For the street, roughly. For the room, no. Outdoor kit against the model: r = 0.51, model 2.2 high, peaks overstated
by 60%. Indoor against the model: r = −0.18. The model is an 11 km cell; it knows the district and nothing about the air
you breathe. That gap is why the sensor exists, and the `agreement` rule states it every day.

## Also learned

Ungasan Kit published no PM2.5 for a week: online radio, dead sensor. Ulu Garden is indoor, seven kilometres away,
offline. The account was a six-sensor network already; the node was reading one.

## Automations

The node switches nothing. `planetai homeassistant` puts every sensor but the public stations, and the latest alert,
into Home Assistant as entities. Build there: purifier on above 35 for ten minutes; a window reminder at the cleanest
hour; a phone notification when the alert level is `act`.
