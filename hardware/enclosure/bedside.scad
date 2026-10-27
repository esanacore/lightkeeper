// Lightkeeper bedside enclosure: Raspberry Pi Zero 2 WH + Waveshare 2.9" Touch e-Paper HAT.
//
// Parametric OpenSCAD model. Two printed parts:
//   part = "bezel"  front bezel with the glass pocket, corner screw bosses and a 15 degree
//                   wedge plinth that leans the display back for reading at a bedside
//   part = "back"   back cover with the cable notch, vents and posts that press the HAT forward
// and two views for documentation:
//   part = "assembly" (default) or "exploded", with reference models of the boards and glass.
//
// Render or export from the command line, for example:
//   openscad -D 'part="bezel"' -o bezel.stl bedside.scad
// tools/render_enclosure.py renders the documentation images and exports both STLs.
//
// Dimensions are millimetres. Sources (see docs/ASSEMBLY.md for the full list):
//   [RPI]  Raspberry Pi Zero 2 W mechanical drawing RP-008358-DS-1
//   [WS]   Waveshare 2.9inch Touch e-Paper HAT size drawing and wiki
// Values marked VERIFY are estimates or typical values that the official drawings do not give.
// Measure them with calipers before printing the final version.
//
// Mechanical facts that shape the design:
// - The HAT has no mounting holes [WS]: its 79.5 x 37.5 driver PCB is bonded to the back of the
//   89.1 x 42.7 glass. So the bezel holds the glass in a pocket, and posts on the back cover
//   press the PCB forward to keep the glass seated.
// - The Pi hangs from the HAT's 40-pin header. Its exact offset under the HAT is not published,
//   so there are no Pi standoffs that could collide; the header carries the Pi, which is fine
//   for a stationary bedside device.
// - The micro-USB power port faces down on the Pi's bottom edge. A straight plug does not fit the
//   space below the Pi, so the BOM calls for a right-angle (90 degree) micro-USB cable that runs
//   along the floor of the case and out through the notch in the back cover.

$fn = 48;

part = "assembly";      // "assembly", "exploded", "bezel", "back"
screen = true;          // draw the reference display content (assembly views only)

// ---- Parts we hold -------------------------------------------------------------------------
glass = [89.1, 42.7, 1.8];        // [WS] outline; thickness VERIFY (raw panel 1.05 + touch layer)
active = [66.89, 29.05];          // [WS] active area, 296 x 128 px
active_offset = [-0.05, 0.05];    // [WS] measured from drawing, about +-0.3: nearly centred
hat_pcb = [79.5, 37.5, 1.6];      // [WS] driver PCB; thickness VERIFY (typical 1.6)
header_gap = 8.5;                 // VERIFY: HAT PCB back to Pi top (typical 2.54 mm female header)
pi = [65, 30, 1.4];               // [RPI] outline; thickness VERIFY (typical 1.4)
pi_corner = 3.5;                  // [RPI] measured corner radius
pi_offset = [0, 0];               // VERIFY: Pi centre relative to glass centre (header position)
pi_below = 2.0;                   // clearance for components on the Pi's underside

// ---- Enclosure -----------------------------------------------------------------------------
tol = 0.4;          // clearance around the glass
wall = 2.0;
front_t = 1.6;      // material in front of the glass
back_t = 2.0;
corner_r = 4.0;     // outer corner radius
window_margin = 0.8;   // the window is the active area plus this on every side
window_chamfer = 1.2;
tilt = 15;          // degrees the display leans back when standing on the plinth
plinth_back = 2.0;  // plinth height at its back end
plinth_tail = 20;   // the plinth runs this far behind the case, so the centre of mass stays
                    // well inside the footprint at the lean angle
screw_pilot = 2.2;  // M2.5 self-tapping pilot
screw_clear = 2.8;
screw_head = 5.0;
boss_d = 4.6;
cable_notch = [13, 7];   // right-angle micro-USB plug body, width x height VERIFY
cable_x = 21.5;          // notch centre; the Pi's power port at x = 54 [RPI], if the Pi is centred
label = ["SECONDARY DISPLAY", "NOT A MEDICAL DEVICE", "CONFIRM ON THE PRIMARY APP"];
label_depth = 0.6;

inner = [glass[0] + 2 * tol, glass[1] + 2 * tol];
inner_depth = glass[2] + hat_pcb[2] + header_gap + pi[2] + pi_below + 1.0;
outer = [inner[0] + 2 * wall, inner[1] + 2 * wall];
bezel_depth = front_t + inner_depth;
plinth_len = bezel_depth + back_t + plinth_tail;
plinth_front = plinth_back + plinth_len * tan(tilt);
boss_xy = [inner[0] / 2 - boss_d / 2 + 1.0, inner[1] / 2 - boss_d / 2 + 1.0];
post_xy = [hat_pcb[0] / 2 - 2.0, hat_pcb[1] / 2 - 2.0];

// Coordinates: y up, z from the front face (z = 0) toward the back. Seen from the front, +x is
// to the viewer's LEFT (seen from the back it is to the right); `cable_x` is in these units.

module rounded_box(size, r, h) {
  hull() for (sx = [-1, 1], sy = [-1, 1])
    translate([sx * (size[0] / 2 - r), sy * (size[1] / 2 - r), 0]) cylinder(r = r, h = h);
}

module corner_points() {
  for (sx = [-1, 1], sy = [-1, 1]) translate([sx * boss_xy[0], sy * boss_xy[1], 0]) children();
}

module bezel() {
  difference() {
    union() {
      difference() {
        rounded_box(outer, corner_r, bezel_depth);
        translate([0, 0, front_t]) rounded_box(inner, 1.0, bezel_depth);   // cavity
        // Viewing window, chamfered so the bezel edge never shadows the active area.
        translate([active_offset[0], active_offset[1], -0.01])
          hull() {
            linear_extrude(0.01)
              square([active[0] + 2 * (window_margin + window_chamfer),
                      active[1] + 2 * (window_margin + window_chamfer)], center = true);
            translate([0, 0, window_chamfer])
              linear_extrude(front_t)
                square([active[0] + 2 * window_margin, active[1] + 2 * window_margin],
                       center = true);
          }
      }
      // Screw bosses in the corners, beside the HAT PCB and behind the glass.
      intersection() {
        rounded_box(outer, corner_r, bezel_depth);
        corner_points()
          translate([0, 0, front_t + glass[2] + 0.3])
            cylinder(d = boss_d, h = bezel_depth - front_t - glass[2] - 0.3);
      }
      plinth();
    }
    corner_points() translate([0, 0, bezel_depth - 8]) cylinder(d = screw_pilot, h = 8.1);
  }
}

// A wedge under the bezel: standing on it, the display leans back by `tilt`.
module plinth() {
  w = outer[0] - 2 * corner_r;
  translate([0, -outer[1] / 2, 0])
    rotate([0, 90, 0])
      linear_extrude(w, center = true)
        polygon([[0, 0], [0, -plinth_front], [-plinth_len, -plinth_back], [-plinth_len, 0]]);
}

module back_cover() {
  lip = 2.0;
  difference() {
    union() {
      rounded_box(outer, corner_r, back_t);
      // Lip that locates the cover inside the bezel.
      translate([0, 0, -lip])
        difference() {
          rounded_box([inner[0] - 2 * tol, inner[1] - 2 * tol], 1.0, lip);
          translate([0, 0, -0.01]) rounded_box([inner[0] - 2 * tol - 3, inner[1] - 2 * tol - 3],
                                               0.5, lip + 0.02);
        }
      // Posts that press the HAT PCB corners forward, clear of the Pi.
      post_len = inner_depth - glass[2] - hat_pcb[2];
      for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * post_xy[0], sy * post_xy[1], -post_len]) cylinder(d = 3.0, h = post_len);
    }
    // Screw holes with counterbores.
    corner_points() {
      translate([0, 0, -lip - 0.1]) cylinder(d = screw_clear, h = back_t + lip + 0.2);
      translate([0, 0, back_t - 1.6]) cylinder(d = screw_head + 0.4, h = 1.7);
    }
    // Clear the bosses with the lip.
    corner_points() translate([0, 0, -lip - 0.1]) cylinder(d = boss_d + 0.6, h = lip + 0.1);
    // Cable notch at the bottom edge for the right-angle micro-USB plug.
    translate([cable_x - cable_notch[0] / 2, -outer[1] / 2 - 0.1, -lip - 0.1])
      cube([cable_notch[0], wall + 2 + cable_notch[1] - 2, back_t + lip + 0.2]);
    // Vents, kept to the upper half so the label below stays whole.
    for (i = [0 : 3])
      translate([0, 4 + i * 4.2, -0.1]) hull() for (sx = [-1, 1])
        translate([sx * 18, 0, 0]) cylinder(d = 2.2, h = back_t + 0.2);
    // The device label HAZ-008 relies on, engraved so it cannot peel off. Read from behind,
    // where +x is the reader's right, so the text needs no mirroring. Kept above the cable notch.
    translate([0, 0, back_t - label_depth])
      linear_extrude(label_depth + 0.1)
        for (i = [0 : len(label) - 1])
          translate([0, -1.5 - i * 4.2, 0])
            text(label[i], size = 2.8, halign = "center", valign = "center",
                 font = "Liberation Sans:style=Bold");
  }
}

// ---- Reference models (not printed) --------------------------------------------------------

module glass_ref() {
  color([0.12, 0.12, 0.13]) cube([glass[0], glass[1], glass[2]], center = true);
  // E-paper surface and, optionally, the real Lightkeeper screen from the rasterizer.
  translate([active_offset[0], active_offset[1], -glass[2] / 2 - 0.01]) {
    color([0.87, 0.86, 0.82]) cube([active[0], active[1], 0.02], center = true);
    if (screen)  // mirrored in x so the text reads correctly from the front
      translate([active[0] / 2, active[1] / 2, -0.03])
        scale([-active[0] / 296, active[1] / 128, 1]) screen_pixels();
  }
}

module hat_pcb_ref() {
  color([0.1, 0.25, 0.55]) cube([hat_pcb[0], hat_pcb[1], hat_pcb[2]], center = true);
}

module pi_ref() {
  color([0.05, 0.42, 0.22]) difference() {
    rounded_box([pi[0], pi[1]], pi_corner, pi[2]);
    for (sx = [-1, 1], sy = [-1, 1])
      translate([sx * (pi[0] / 2 - 3.5), sy * (pi[1] / 2 - 3.5), -0.1]) cylinder(d = 2.75, h = 2);
  }
  // 40-pin header, above the board along the top long edge [RPI].
  color([0.08, 0.08, 0.08]) translate([-25.5, pi[1] / 2 - 6, -header_gap])
    cube([51, 5, header_gap]);
}

module screen_pixels() {
  // Generated: one box per run of ink pixels, rows counted down from the top-left.
  color([0.07, 0.07, 0.08]) for (r = SCREEN_RUNS) translate([r[1], -r[0] - 1, 0]) cube([r[2], 1, 0.02]);
}

include <screen_in_range.scad>

// ---- Views ---------------------------------------------------------------------------------

// Parts in their real order from the front: bezel, glass, HAT PCB, Pi, back cover. `explode`
// pulls the bezel toward the viewer and the rest backward.
module stack(explode = 0) {
  translate([0, 0, -explode * 2.4]) color([0.93, 0.93, 0.91]) bezel();
  translate([0, 0, front_t + glass[2] / 2]) glass_ref();
  translate([0, 0, front_t + glass[2] + hat_pcb[2] / 2 + explode * 0.8]) hat_pcb_ref();
  translate([pi_offset[0], pi_offset[1],
             front_t + glass[2] + hat_pcb[2] + header_gap + explode * 2.0]) pi_ref();
  translate([0, 0, bezel_depth + explode * 3.6]) color([0.86, 0.86, 0.84]) back_cover();
}

// Views are turned from this model's y-up frame into OpenSCAD's z-up world. The assembly stands
// on its plinth at the real lean angle, on a table surface; the exploded view stays upright.
floor_z = (-outer[1] / 2 - plinth_front) * cos(tilt);

if (part == "bezel") {
  bezel();                              // prints face down, as exported
} else if (part == "back") {
  rotate([180, 0, 0]) back_cover();     // prints outer face down, posts up
} else if (part == "exploded") {
  rotate([90, 0, 0]) stack(explode = 12);
} else {
  rotate([90 + tilt, 0, 0]) stack();
  color([0.80, 0.78, 0.74]) translate([0, -25, floor_z - 1.5]) cube([220, 170, 3], center = true);
}
