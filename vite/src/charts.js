// Dashboard charts. Loaded only by admin/dashboard.html, which is the only
// page with a chart on it -- hence a Vite entry of its own rather than a slice
// of main.js, which every page pays for.
//
// This replaces d3 3.5.14 + nvd3 1.8.2-dev (147K gzipped, unmaintained since
// 2017) with uPlot (21K). The zoom, the legend toggle and the cursor readout
// below are all uPlot's own; nvd3 needed a second chart underneath as a brush
// strip because it could not zoom at all.

import uPlot from "uplot";

const HEIGHT = 320;

// The design system's ink and rule colours (theme.css). Read at draw time
// rather than hardcoded, so a change to the tokens carries here too.
function token(name, fallback) {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return value || fallback;
}

// A <script type="application/json"> block: data, never executed, so it needs
// no CSP exemption the way an inline <script> would.
function payload(id) {
  const el = document.getElementById(id);
  return el ? JSON.parse(el.textContent) : null;
}

const fmtDay = uPlot.fmtDate("{D} {MMM} {YYYY}");

const DAY = 3600 * 24;

// uPlot's default day tier reads "4/28", which is 4 April to half the people
// who use this and 28 April to the other half. Same table as uPlot's own, with
// the day-and-month stamps written unambiguously.
//   tick incr | default | year | month | day | hour | min | sec | mode
const TIME_STAMPS = [
  [DAY * 365, "{YYYY}", null, null, null, null, null, null, 1],
  [DAY * 28, "{MMM}", "\n{YYYY}", null, null, null, null, null, 1],
  [DAY, "{D} {MMM}", "\n{YYYY}", null, null, null, null, null, 1],
  [3600, "{HH}", "\n{D} {MMM} {YY}", null, "\n{D} {MMM}", null, null, null, 1],
  [60, "{HH}:{mm}", "\n{D} {MMM} {YY}", null, "\n{D} {MMM}", null, null, null, 1],
  [1, ":{ss}", "\n{D} {MMM} {YY} {HH}:{mm}", null, "\n{D} {MMM} {HH}:{mm}", null, "\n{HH}:{mm}", null, 1],
];

// uPlot's legend doubles as the tooltip, and prints "--" whenever the cursor is
// off the plot. On a dashboard that is most of the time, and it wastes the one
// place on the page where the current figures could be: fall back to the last
// point instead, so the legend reads as a headline until you hover.
function readValue(format) {
  return (u, _raw, seriesIdx, idx) => {
    const at = idx ?? u.data[0].length - 1;
    const value = u.data[seriesIdx][at];
    return value == null ? "--" : format(value);
  };
}

const readDate = readValue((seconds) => fmtDay(new Date(seconds * 1000)));
const readCount = readValue(String);

// Users and connections are both counts, so a fractional gridline is a lie.
function wholeNumbers(_u, splits) {
  return splits.map((v) => (Number.isInteger(v) ? v : null));
}

function baseOptions(series) {
  const ink = token("--color-gray-500", "#6b7280");
  const rule = token("--color-gray-200", "#e5e7eb");

  return {
    height: HEIGHT,
    // Drag a range on the plot to zoom, double-click to reset. This is what
    // the old brush strip existed to provide.
    cursor: { drag: { x: true, y: false } },
    scales: {
      // Counts start at zero; a truncated axis makes 1 look like none. Keep a
      // headroom of 1 so a flat series is not drawn on the frame itself.
      y: { range: (u, _min, max) => [0, Math.max(max, 1)] },
    },
    axes: [
      {
        stroke: ink,
        grid: { stroke: rule, width: 1 },
        ticks: { stroke: rule },
        values: TIME_STAMPS,
      },
      {
        stroke: ink,
        grid: { stroke: rule, width: 1 },
        ticks: { stroke: rule },
        incrs: [1, 2, 5, 10, 25, 50, 100, 250, 500, 1000],
        filter: wholeNumbers,
        size: 40,
      },
    ],
    series,
  };
}

function draw(el, opts, data) {
  const chart = new uPlot({ ...opts, width: el.clientWidth }, data, el);
  new ResizeObserver(() => {
    chart.setSize({ width: el.clientWidth, height: HEIGHT });
  }).observe(el);
  // uPlot draws to a canvas, so the axes and the zoom level leave no DOM behind
  // to read. Hang the instance off its container: it is the only handle another
  // script -- or the browser console -- has on the chart's state.
  el.uplot = chart;
  return chart;
}

// --- Users: registered, active and new, on one shared grid of months. -------
//
// One y scale for all three: they all count users, so a second scale would
// only invent a relationship between them. Registered dwarfs the other two,
// which is the fact -- click it off in the legend to read the small ones.

function usersChart() {
  const el = document.getElementById("chart-users");
  const spec = payload("chart-users-data");
  if (!el || !spec || !spec.data[0].length) return;

  const opts = baseOptions([
    { label: spec.x_label, value: readDate },
    ...spec.series.map((s) => ({
      label: s.label,
      stroke: s.stroke,
      width: 2,
      points: { show: false },
      value: readCount,
    })),
  ]);
  draw(el, opts, spec.data);
}

// --- Unique connections: one measure, three grains. --------------------------
//
// Daily, weekly and monthly are the same quantity at different resolutions, so
// they are a switch rather than three lines to overlay -- overlaid, the legend
// invites a comparison that means nothing.

function connectionsChart() {
  const el = document.getElementById("chart-connections");
  const spec = payload("chart-connections-data");
  if (!el || !spec) return;

  const grains = spec.grains.filter((g) => g.data[0].length);
  if (!grains.length) return;

  // The series keeps one stable label across the three grains: uPlot builds the
  // legend once from series[].label and never reads it again, and the pressed
  // button already says which grain is on screen.
  const opts = baseOptions([
    { label: spec.x_label, value: readDate },
    {
      label: spec.label,
      stroke: spec.stroke,
      width: 2,
      points: { show: false },
      value: readCount,
    },
  ]);
  const chart = draw(el, opts, grains[0].data);

  el.prepend(grainSwitch(grains, (grain) => chart.setData(grain.data)));
}

function grainSwitch(grains, onPick) {
  const group = document.createElement("div");
  group.className = "chart-grains";
  group.setAttribute("role", "group");

  const buttons = grains.map((grain, i) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = grain.label;
    button.setAttribute("aria-pressed", String(i === 0));
    button.addEventListener("click", () => {
      buttons.forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      onPick(grain);
    });
    group.append(button);
    return button;
  });

  return group;
}

usersChart();
connectionsChart();
