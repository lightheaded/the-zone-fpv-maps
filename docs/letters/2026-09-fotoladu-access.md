# Draft: request to Maa- ja Ruumiamet for oblique photo access

Status: draft, not sent. Decided worth sending on 2026-09-13, after the proof of
concept in `docs/facades.md` showed that the buildings come out recognisable.

Send to: fotoladu@maaruum.ee

Two notes before sending.

1. **Say what has already been done.** The proof of concept read Deep Zoom tiles from
   the viewer, which the licensing note asks not to do at scale. Saying so first is
   better than being found out, and it is also the strongest argument that the
   request is real work and not a fishing trip.
2. **Ask for orientation data, not only the images.** The images alone cost a
   resection per photo, which is the step that is only right about half the time. The
   camera position and angles are what make the result reliable, and the agency
   already holds them.

Write it in Estonian when sending. This draft is in English so that it can live in a
repository that is written in English.

---

**Subject:** Kaldaerofotode kasutamine avatud lähtekoodiga droonisimulaatori kaartidel

Tere,

I build maps of real places for the FPV drone simulator The Zone, as an open source
hobby project. The pipeline turns your open geodata into one glTF file per map. It
uses the 1 m elevation model, the 10 cm city orthophoto, the LOD2 building model and,
most recently, the aerial lidar. Everything is published under Apache-2.0 with the
attribution your open data licence asks for, at
https://github.com/lightheaded/the-zone-fpv-maps

The LOD2 model gives every building its shape and nothing of its surface, so a map of
Tartu today has 23745 identical concrete houses. Your oblique photos hold the facades
of all of them. I have built a working pipeline that recovers a camera from the four
ground corners your API publishes, checks the result against the orthophoto, and bakes
the facades onto the building walls. Over the Tartu old town it reaches 60 percent of
the wall area, and the buildings are recognisable.

I have two requests.

**1. Bulk access to the frames.** The viewer serves each photo as Deep Zoom tiles and
offers no export. My proof of concept therefore stitched tiles from the viewer, at
proof of concept volume, for one square kilometre of the old town. I would rather not
do that at any larger scale without your agreement, which is why I am writing. Is
there a way to obtain the original frames for a named list of photos?

**2. The exterior orientation data.** Your API gives the four ground corners of a
frame and neither the camera position nor its angles. Four points on the ground barely
determine a camera, so I recover them by a fit that is ambiguous: several readings of
the same four corners fit to under a pixel and are different cameras. I resolve it by
correlating against the orthophoto, which works and is a great deal of machinery to
replace a number you already have. The projection centre, the three rotation angles
and the calibrated focal length for each frame would remove the whole step.

What the project would do with them:

- Publish the maps under the attribution "Foto: Maa- ja Ruumiamet", together with the
  attribution for the other data sets.
- Publish the method as documentation, which it already does.
- Keep to whatever conditions you set on volume, on caching and on which photos.

If facade textures cannot be redistributed at all, that is a useful answer too, and I
will keep the capability local and say so in the licensing notes.

Ette tänades,

