# AMR Health Care — Clinic Management 🏥

Chanchal Court More, Chanchal, Malda · **Management software help: 7602292599**

Ye software Green Life wale software jaisa hi hai, lekin naam, logo, address aur phone **AMR Health Care** ke hain. Iska database aur website **bilkul alag** hai.

## Kya-kya hai
- OPD slip, Lab bill, Combined bill (OPD + Lab) — sab AMR ke naam se.
- **Lab Report:** bill ke tests ka report — Patient box, DEPARTMENT, TEST NAME / RESULT / UNIT / NORMAL RANGE, H/L flag, "Checked By" Lab Technician aur Doctor ka signature, neeche AMR ka address footer. Normal ranges pehle se bhari hain (Admin kisi bhi test ka layout badal ke save kar sakta hai).
- **Referring Doctors + Commission:** jo doctor patient bhejta hai uska naam, degree, WhatsApp number aur commission (% ya fixed ₹) Admin → **Referring Doctors** mein daalein. Lab bill banate waqt **Referred by** se doctor chunein — report par "Referring By" apne aap aata hai, aur bill banate hi **Save & message doctor** se us doctor ko WhatsApp message jata hai (patient ka naam aur tests; rate ya commission message mein nahi likha jata). **Commission** page par date-wise doctor-wise: kitne patients, kitna billed, kitna commission, kitna paid/due — "Mark paid", WhatsApp statement aur Excel CSV bhi. Commission sirf Admin dekhta hai (kisi aur ko dena ho to Users mein "Commission" tick karein).
- **Report Signers:** Dr. S. Kumar aur Abu Sufian ke naam pehle se hain. Admin → **Report Signers** mein unke signature ki photo upload karein. Naya doctor aaye to wahin se add karein.
- **Users + Permissions:** Admin har user ke liye tick karta hai ki wo kya-kya kar sakta hai.
- QR se patient self-booking, WhatsApp slip, online + offline dono, backup, audit log — Green Life jaisa.

## Pehli baar login
Admin PIN **1234**, Reception PIN **1111**, Lab PIN **2222** — login ke baad **Users** page se badal dein, aur har desk ka alag user banayein.

## Sabse pehle (Admin)
1. **Tests & Rates:** abhi Green Life wali rates bhari hain. AMR ki apni rate list ho to Excel se copy karke **Import rates** mein paste karein (test ka naam, phir rate).
2. **Doctors:** Green Life wale 13 doctors pehle se bhare hain. AMR ke hisaab se fees (abhi ₹300) aur din/timing badal dein, ya hata/jod dein.
3. **Referring Doctors:** jo doctors patient bhejte hain unhe jodein (naam, phone, commission).
4. **Settings:** logo upload karein, aur zaroorat ho to report ka header/footer image.
5. **Report Signers:** signature photos upload karein.
6. **Lab report ki ranges** apne pathologist se ek baar check karwa lein.

## 🌐 Online karna (alag GitHub + Render, Supabase wahi chalega)
1. GitHub par **naya repository** (jaise `amr-healthcare`) banayein. Ye saari 11 files upload karein: `app.py`, `qr.py`, `requirements.txt`, `Procfile`, `runtime.txt`, `README.md`, `index.html`, `book.html`, `sw.js`, `manifest.json`, `icon.svg`.
2. Render par **naya Web Service** banayein (Build: `pip install -r requirements.txt`, Start: `gunicorn app:app`, Free).
3. **Environment Variable:** `DATABASE_URL` = wahi Supabase (Session pooler) connection string jo Green Life mein use ki hai. AMR ka data apne aap alag table (`amr_records`) mein jayega, Green Life ke saath nahi milega.
4. Deploy ke baad `https://<aapka-link>/api/ping` kholkar `{"ok": true}` check karein, phir login karein.
5. Har computer ko Settings mein alag code (1, 2, 3) dein.

## ⚠️ Dhyan rakhein
- **Patient ID** abhi `AMR/1, AMR/2…` se shuru hota hai. Purani series (jaise AMR/1351) se aage badhana ho to bata dein. Agar ek se zyada computer par bill banega to Settings mein Patient ID format `AMR/{d}-{n}` kar dein, taaki number repeat na ho.
- Software ka link sirf staff ko dein. Har hafte **Backup & Sync → Download backup** karein.

Madad ke liye: **7602292599**
