/**
 * Handoff bulk uploader for 1835 Onslow Dr — runs in the Handoff page DevTools console.
 *
 * Prereqs:
 *   1. magicplan-webhook is deployed with the new /file endpoint
 *   2. FILE_FETCH_TOKEN is set on Railway and you know the value
 *   3. You're on https://app.handoff.ai/projects/7d7e19aa-524b-4033-856c-b9dcea192172?tab=files
 *
 * Usage:
 *   - Open DevTools (Cmd+Opt+I) → Console
 *   - Edit the FILE_FETCH_TOKEN constant below to your real token
 *   - Paste this whole file, press Enter
 *   - Watch progress in the console; uploads appear in the Files tab as they complete
 *   - To stop early: window.__cwUploadStop = true
 */
(async () => {
  // ---- EDIT ME ----
  const FILE_FETCH_TOKEN = 'PASTE_YOUR_TOKEN_HERE';
  // -----------------

  const ENDPOINT = 'https://magicplan-webhook-production.up.railway.app/file';
  const PACING_MS = 1500; // delay between uploads so Handoff's queue keeps up
  const FILES = [
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PLANS/New River Apartment Report.pdf",
    "name": "New River Apartment Report.pdf",
    "type": "application/pdf",
    "size": 1503492
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PLANS/New River Apartment Sketch.pdf",
    "name": "New River Apartment Sketch.pdf",
    "type": "application/pdf",
    "size": 50007
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 1.mp4",
    "name": "1st Floor - Bathroom - 1.mp4",
    "type": "video/mp4",
    "size": 9237045
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 2.jpg",
    "name": "1st Floor - Bathroom - 2.jpg",
    "type": "image/jpeg",
    "size": 165379
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 3.jpg",
    "name": "1st Floor - Bathroom - 3.jpg",
    "type": "image/jpeg",
    "size": 229466
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 4.jpg",
    "name": "1st Floor - Bathroom - 4.jpg",
    "type": "image/jpeg",
    "size": 219585
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 5.jpg",
    "name": "1st Floor - Bathroom - 5.jpg",
    "type": "image/jpeg",
    "size": 189877
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 6.jpg",
    "name": "1st Floor - Bathroom - 6.jpg",
    "type": "image/jpeg",
    "size": 163624
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 7.jpg",
    "name": "1st Floor - Bathroom - 7.jpg",
    "type": "image/jpeg",
    "size": 261549
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 8.jpg",
    "name": "1st Floor - Bathroom - 8.jpg",
    "type": "image/jpeg",
    "size": 248601
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bathroom - 9.jpg",
    "name": "1st Floor - Bathroom - 9.jpg",
    "type": "image/jpeg",
    "size": 167686
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom (2) - 1.jpg",
    "name": "1st Floor - Bedroom (2) - 1.jpg",
    "type": "image/jpeg",
    "size": 305725
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom (2) - 2.jpg",
    "name": "1st Floor - Bedroom (2) - 2.jpg",
    "type": "image/jpeg",
    "size": 229710
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom (2) - 3.mp4",
    "name": "1st Floor - Bedroom (2) - 3.mp4",
    "type": "video/mp4",
    "size": 8669651
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom (2) - 4.jpg",
    "name": "1st Floor - Bedroom (2) - 4.jpg",
    "type": "image/jpeg",
    "size": 267304
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom (2) - 5.jpg",
    "name": "1st Floor - Bedroom (2) - 5.jpg",
    "type": "image/jpeg",
    "size": 271512
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom (2) - 6.jpg",
    "name": "1st Floor - Bedroom (2) - 6.jpg",
    "type": "image/jpeg",
    "size": 315421
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom (2) - 7.jpg",
    "name": "1st Floor - Bedroom (2) - 7.jpg",
    "type": "image/jpeg",
    "size": 380981
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 1.jpg",
    "name": "1st Floor - Bedroom - 1.jpg",
    "type": "image/jpeg",
    "size": 254852
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 10.jpg",
    "name": "1st Floor - Bedroom - 10.jpg",
    "type": "image/jpeg",
    "size": 267079
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 11.jpg",
    "name": "1st Floor - Bedroom - 11.jpg",
    "type": "image/jpeg",
    "size": 292627
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 12.mp4",
    "name": "1st Floor - Bedroom - 12.mp4",
    "type": "video/mp4",
    "size": 7386457
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 2.jpg",
    "name": "1st Floor - Bedroom - 2.jpg",
    "type": "image/jpeg",
    "size": 309229
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 3.jpg",
    "name": "1st Floor - Bedroom - 3.jpg",
    "type": "image/jpeg",
    "size": 216672
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 4.jpg",
    "name": "1st Floor - Bedroom - 4.jpg",
    "type": "image/jpeg",
    "size": 278820
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 5.jpg",
    "name": "1st Floor - Bedroom - 5.jpg",
    "type": "image/jpeg",
    "size": 311898
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 6.jpg",
    "name": "1st Floor - Bedroom - 6.jpg",
    "type": "image/jpeg",
    "size": 279302
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 7.jpg",
    "name": "1st Floor - Bedroom - 7.jpg",
    "type": "image/jpeg",
    "size": 279027
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 8.jpg",
    "name": "1st Floor - Bedroom - 8.jpg",
    "type": "image/jpeg",
    "size": 236188
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Bedroom - 9.jpg",
    "name": "1st Floor - Bedroom - 9.jpg",
    "type": "image/jpeg",
    "size": 213562
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet (2) - 1.jpg",
    "name": "1st Floor - Closet (2) - 1.jpg",
    "type": "image/jpeg",
    "size": 258582
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet (2) - 2.jpg",
    "name": "1st Floor - Closet (2) - 2.jpg",
    "type": "image/jpeg",
    "size": 254844
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet (2) - 3.jpg",
    "name": "1st Floor - Closet (2) - 3.jpg",
    "type": "image/jpeg",
    "size": 212260
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet (2) - 4.jpg",
    "name": "1st Floor - Closet (2) - 4.jpg",
    "type": "image/jpeg",
    "size": 231349
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet (2) - 5.jpg",
    "name": "1st Floor - Closet (2) - 5.jpg",
    "type": "image/jpeg",
    "size": 245374
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet (2) - 6.jpg",
    "name": "1st Floor - Closet (2) - 6.jpg",
    "type": "image/jpeg",
    "size": 263034
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet - 1.jpg",
    "name": "1st Floor - Closet - 1.jpg",
    "type": "image/jpeg",
    "size": 238270
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet - 2.jpg",
    "name": "1st Floor - Closet - 2.jpg",
    "type": "image/jpeg",
    "size": 218695
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet - 3.jpg",
    "name": "1st Floor - Closet - 3.jpg",
    "type": "image/jpeg",
    "size": 228792
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet - 4.jpg",
    "name": "1st Floor - Closet - 4.jpg",
    "type": "image/jpeg",
    "size": 208188
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet - 5.jpg",
    "name": "1st Floor - Closet - 5.jpg",
    "type": "image/jpeg",
    "size": 247211
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet - 6.jpg",
    "name": "1st Floor - Closet - 6.jpg",
    "type": "image/jpeg",
    "size": 202302
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Closet - 7.jpg",
    "name": "1st Floor - Closet - 7.jpg",
    "type": "image/jpeg",
    "size": 210270
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 1.jpg",
    "name": "1st Floor - Furnace Room - 1.jpg",
    "type": "image/jpeg",
    "size": 294603
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 2.jpg",
    "name": "1st Floor - Furnace Room - 2.jpg",
    "type": "image/jpeg",
    "size": 274390
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 3.jpg",
    "name": "1st Floor - Furnace Room - 3.jpg",
    "type": "image/jpeg",
    "size": 248763
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 4.jpg",
    "name": "1st Floor - Furnace Room - 4.jpg",
    "type": "image/jpeg",
    "size": 187206
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 5.jpg",
    "name": "1st Floor - Furnace Room - 5.jpg",
    "type": "image/jpeg",
    "size": 207838
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 6.jpg",
    "name": "1st Floor - Furnace Room - 6.jpg",
    "type": "image/jpeg",
    "size": 227638
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 7.jpg",
    "name": "1st Floor - Furnace Room - 7.jpg",
    "type": "image/jpeg",
    "size": 343089
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 8.jpg",
    "name": "1st Floor - Furnace Room - 8.jpg",
    "type": "image/jpeg",
    "size": 282092
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Furnace Room - 9.jpg",
    "name": "1st Floor - Furnace Room - 9.jpg",
    "type": "image/jpeg",
    "size": 212253
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 1.jpg",
    "name": "1st Floor - Kitchen - 1.jpg",
    "type": "image/jpeg",
    "size": 399500
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 10.jpg",
    "name": "1st Floor - Kitchen - 10.jpg",
    "type": "image/jpeg",
    "size": 408502
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 11.jpg",
    "name": "1st Floor - Kitchen - 11.jpg",
    "type": "image/jpeg",
    "size": 353267
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 12.jpg",
    "name": "1st Floor - Kitchen - 12.jpg",
    "type": "image/jpeg",
    "size": 386077
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 13.jpg",
    "name": "1st Floor - Kitchen - 13.jpg",
    "type": "image/jpeg",
    "size": 294942
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 14.jpg",
    "name": "1st Floor - Kitchen - 14.jpg",
    "type": "image/jpeg",
    "size": 303855
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 15.jpg",
    "name": "1st Floor - Kitchen - 15.jpg",
    "type": "image/jpeg",
    "size": 430656
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 2.jpg",
    "name": "1st Floor - Kitchen - 2.jpg",
    "type": "image/jpeg",
    "size": 275897
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 3.jpg",
    "name": "1st Floor - Kitchen - 3.jpg",
    "type": "image/jpeg",
    "size": 257489
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 4.jpg",
    "name": "1st Floor - Kitchen - 4.jpg",
    "type": "image/jpeg",
    "size": 324028
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 5.jpg",
    "name": "1st Floor - Kitchen - 5.jpg",
    "type": "image/jpeg",
    "size": 412785
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 6.mp4",
    "name": "1st Floor - Kitchen - 6.mp4",
    "type": "video/mp4",
    "size": 8161623
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 7.jpg",
    "name": "1st Floor - Kitchen - 7.jpg",
    "type": "image/jpeg",
    "size": 247969
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 8.jpg",
    "name": "1st Floor - Kitchen - 8.jpg",
    "type": "image/jpeg",
    "size": 263533
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Kitchen - 9.jpg",
    "name": "1st Floor - Kitchen - 9.jpg",
    "type": "image/jpeg",
    "size": 271332
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Living Room - 1.mp4",
    "name": "1st Floor - Living Room - 1.mp4",
    "type": "video/mp4",
    "size": 17693828
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Living Room - 2.jpg",
    "name": "1st Floor - Living Room - 2.jpg",
    "type": "image/jpeg",
    "size": 283811
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Living Room - 3.jpg",
    "name": "1st Floor - Living Room - 3.jpg",
    "type": "image/jpeg",
    "size": 214670
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Living Room - 4.jpg",
    "name": "1st Floor - Living Room - 4.jpg",
    "type": "image/jpeg",
    "size": 300899
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Living Room - 5.jpg",
    "name": "1st Floor - Living Room - 5.jpg",
    "type": "image/jpeg",
    "size": 330488
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Living Room - 6.mp4",
    "name": "1st Floor - Living Room - 6.mp4",
    "type": "video/mp4",
    "size": 10693288
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Living Room - 7.jpg",
    "name": "1st Floor - Living Room - 7.jpg",
    "type": "image/jpeg",
    "size": 373166
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other (2) - 1.jpg",
    "name": "1st Floor - Other (2) - 1.jpg",
    "type": "image/jpeg",
    "size": 209933
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other (2) - 2.jpg",
    "name": "1st Floor - Other (2) - 2.jpg",
    "type": "image/jpeg",
    "size": 340217
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other (2) - 3.jpg",
    "name": "1st Floor - Other (2) - 3.jpg",
    "type": "image/jpeg",
    "size": 223824
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other (2) - 4.jpg",
    "name": "1st Floor - Other (2) - 4.jpg",
    "type": "image/jpeg",
    "size": 298825
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other (2) - 5.jpg",
    "name": "1st Floor - Other (2) - 5.jpg",
    "type": "image/jpeg",
    "size": 358439
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other (2) - 6.jpg",
    "name": "1st Floor - Other (2) - 6.jpg",
    "type": "image/jpeg",
    "size": 266605
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other (2) - 7.jpg",
    "name": "1st Floor - Other (2) - 7.jpg",
    "type": "image/jpeg",
    "size": 235327
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 1.jpg",
    "name": "1st Floor - Other - 1.jpg",
    "type": "image/jpeg",
    "size": 316753
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 2.jpg",
    "name": "1st Floor - Other - 2.jpg",
    "type": "image/jpeg",
    "size": 286339
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 3.jpg",
    "name": "1st Floor - Other - 3.jpg",
    "type": "image/jpeg",
    "size": 322052
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 4.jpg",
    "name": "1st Floor - Other - 4.jpg",
    "type": "image/jpeg",
    "size": 376294
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 5.jpg",
    "name": "1st Floor - Other - 5.jpg",
    "type": "image/jpeg",
    "size": 325583
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 6.jpg",
    "name": "1st Floor - Other - 6.jpg",
    "type": "image/jpeg",
    "size": 402459
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 7.jpg",
    "name": "1st Floor - Other - 7.jpg",
    "type": "image/jpeg",
    "size": 345939
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 8.jpg",
    "name": "1st Floor - Other - 8.jpg",
    "type": "image/jpeg",
    "size": 349080
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/1st Floor - Other - 9.mp4",
    "name": "1st Floor - Other - 9.mp4",
    "type": "video/mp4",
    "size": 22303067
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment (2) - 1.mp4",
    "name": "New River Apartment (2) - 1.mp4",
    "type": "video/mp4",
    "size": 15281872
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment (2) - 2.mp4",
    "name": "New River Apartment (2) - 2.mp4",
    "type": "video/mp4",
    "size": 15502768
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment (2) - 3.mp4",
    "name": "New River Apartment (2) - 3.mp4",
    "type": "video/mp4",
    "size": 14482214
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment (2) - 4.mp4",
    "name": "New River Apartment (2) - 4.mp4",
    "type": "video/mp4",
    "size": 9995560
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 1.jpg",
    "name": "New River Apartment - 1.jpg",
    "type": "image/jpeg",
    "size": 382494
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 10.jpg",
    "name": "New River Apartment - 10.jpg",
    "type": "image/jpeg",
    "size": 720367
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 11.jpg",
    "name": "New River Apartment - 11.jpg",
    "type": "image/jpeg",
    "size": 926325
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 12.jpg",
    "name": "New River Apartment - 12.jpg",
    "type": "image/jpeg",
    "size": 923277
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 13.jpg",
    "name": "New River Apartment - 13.jpg",
    "type": "image/jpeg",
    "size": 1038602
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 2.jpg",
    "name": "New River Apartment - 2.jpg",
    "type": "image/jpeg",
    "size": 902992
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 3.jpg",
    "name": "New River Apartment - 3.jpg",
    "type": "image/jpeg",
    "size": 640701
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 4.jpg",
    "name": "New River Apartment - 4.jpg",
    "type": "image/jpeg",
    "size": 712672
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 5.jpg",
    "name": "New River Apartment - 5.jpg",
    "type": "image/jpeg",
    "size": 920801
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 6.jpg",
    "name": "New River Apartment - 6.jpg",
    "type": "image/jpeg",
    "size": 1066967
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 7.jpg",
    "name": "New River Apartment - 7.jpg",
    "type": "image/jpeg",
    "size": 707636
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 8.jpg",
    "name": "New River Apartment - 8.jpg",
    "type": "image/jpeg",
    "size": 866376
  },
  {
    "path": "/TRUBILT/JOBS/Brynn Marr Homes/1835 ONSLOW DR/PICTURES/EXISTING CONDITIONS/New River Apartment - 9.jpg",
    "name": "New River Apartment - 9.jpg",
    "type": "image/jpeg",
    "size": 252231
  }
];

  if (FILE_FETCH_TOKEN === 'PASTE_YOUR_TOKEN_HERE') {
    console.error('Set FILE_FETCH_TOKEN in the script before running.');
    return;
  }

  const input = document.querySelector('input[type="file"]');
  if (!input) {
    console.error('No file input found on this page. Are you on the Files tab?');
    return;
  }

  console.log(`Starting upload of ${FILES.length} files. Stop with: window.__cwUploadStop = true`);
  let ok = 0, fail = 0;
  const t0 = Date.now();

  for (let i = 0; i < FILES.length; i++) {
    if (window.__cwUploadStop) { console.warn('Stopped by user.'); break; }
    const f = FILES[i];
    const tag = `[${i + 1}/${FILES.length}]`;
    try {
      const url = `${ENDPOINT}?path=${encodeURIComponent(f.path)}`;
      const resp = await fetch(url, {
        headers: { 'X-Auth-Token': FILE_FETCH_TOKEN },
      });
      if (!resp.ok) {
        const text = await resp.text().catch(() => '');
        console.error(`${tag} FAIL ${f.name}: HTTP ${resp.status} ${text.slice(0, 200)}`);
        fail++;
        continue;
      }
      const blob = await resp.blob();
      if (blob.size !== f.size) {
        console.warn(`${tag} size mismatch: expected ${f.size}, got ${blob.size} for ${f.name}`);
      }
      const file = new File([blob], f.name, { type: f.type });
      const dt = new DataTransfer();
      dt.items.add(file);
      Object.defineProperty(input, 'files', { value: dt.files, configurable: true });
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      ok++;
      const elapsed = ((Date.now() - t0) / 1000).toFixed(0);
      console.log(`${tag} ✓ ${f.name} (${(blob.size / 1024).toFixed(0)} KB) — total ok=${ok} fail=${fail} ${elapsed}s`);
    } catch (e) {
      fail++;
      console.error(`${tag} ERROR ${f.name}:`, e);
    }
    await new Promise(r => setTimeout(r, PACING_MS));
  }

  const elapsed = ((Date.now() - t0) / 1000).toFixed(0);
  console.log(`DONE — ok=${ok} fail=${fail} in ${elapsed}s`);
})();
