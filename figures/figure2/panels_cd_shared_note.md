# Figure 2c--d shared-axis note

Panels c and d are rendered natively on one 8.27 × 4.35 inch Matplotlib canvas.
Their GridSpec widths follow a 3:2 ratio, with Panel d two-thirds as wide as
Panel c. They use the same y-axis object, so each Panel-d connector is centered
on the corresponding Panel-c city row. City rows are sorted in descending order
by Panel d's observed new-building PV area per newly observed building; `All
cities` is the final separated row. No standalone panel image or PDF is
rasterized into this shared page. Panel c's heatmap body uses Matplotlib's
intentional image artist while all labels, points, lines and axes remain vector
in the PDF. Scientific evidence status: REPRODUCED.
