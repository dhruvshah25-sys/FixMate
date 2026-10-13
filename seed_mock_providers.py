"""Add realistic demo providers to FixMate's SQLite database.

Run from the FixMate project folder:
    python seed_mock_providers.py
Safe to rerun: records are matched by their mock email addresses and updated,
not duplicated. Existing consumer accounts, requests, bookings and reviews are untouched.
"""
from app import get_db, init_db
from werkzeug.security import generate_password_hash

PASSWORD = "FixMateDemo123!"
PROVIDERS = [
    # name, phone, experience, description, area, verified, [(category, price), ...]
    ("Arjun Patil", "9000001001", 12, "Experienced plumber for leaks, taps, and bathroom fittings.", "Malad", 1, [("Plumbing", 450)]),
    ("Rohit Sharma", "9000001002", 8, "Electrical repairs, switches, fans, and lighting installation.", "Goregaon", 1, [("Electrical", 500)]),
    ("Imran Shaikh", "9000001003", 10, "Carpentry, cupboard repairs, hinges, and custom shelves.", "Kandivali", 1, [("Carpentry", 650)]),
    ("Sagar More", "9000001004", 7, "AC servicing, cooling issues, and installation support.", "Malad West", 1, [("AC Repair", 700)]),
    ("Vikram Yadav", "9000001005", 9, "Home painting, touch-ups, and wall finishing.", "Borivali", 1, [("Painting", 800)]),
    ("Nilesh Jadhav", "9000001006", 6, "Repairs for mixers, microwaves, and small household appliances.", "Goregaon East", 1, [("Appliance Repair", 550)]),
    ("Aamir Khan", "9000001007", 5, "RO water purifier servicing and filter replacement.", "Malad", 1, [("RO Repair", 400)]),
    ("Prakash Sawant", "9000001008", 11, "Washing machine diagnosis and repair for common brands.", "Kandivali East", 1, [("Washing Machine Repair", 600)]),
    ("Deepak Verma", "9000001009", 13, "Refrigerator cooling, compressor checks, and maintenance.", "Goregaon", 1, [("Refrigerator Repair", 750)]),
    ("Manoj Gupta", "9000001010", 4, "Pest control for ants, cockroaches, and household insects.", "Malad East", 1, [("Pest Control", 650)]),
    ("Kunal Desai", "9000001011", 3, "Quick plumbing fixes and tap or flush replacement.", "Kandivali", 1, [("Plumbing", 350), ("RO Repair", 450)]),
    ("Ramesh Chavan", "9000001012", 15, "Residential electrician for wiring and electrical faults.", "Borivali", 1, [("Electrical", 650), ("Appliance Repair", 600)]),
    ("Farhan Memon", "9000001013", 7, "Furniture assembly, door alignment, and wood repairs.", "Malad West", 1, [("Carpentry", 500)]),
    ("Ajay Tiwari", "9000001014", 6, "AC cleaning and basic split AC troubleshooting.", "Goregaon West", 1, [("AC Repair", 550)]),
    ("Mahesh Pawar", "9000001015", 14, "Interior and exterior painting with neat finishing.", "Kandivali West", 1, [("Painting", 950)]),
    ("Sohail Ansari", "9000001016", 2, "Small appliance troubleshooting and repair.", "Malad", 0, [("Appliance Repair", 400)]),
    ("Ganesh Naik", "9000001017", 5, "Washing machine installation and repair.", "Goregaon East", 0, [("Washing Machine Repair", 500)]),
    ("Ravi Kumar", "9000001018", 9, "Refrigerator servicing and cooling maintenance.", "Borivali East", 1, [("Refrigerator Repair", 650)]),
    ("Dinesh Koli", "9000001019", 4, "General pest treatment for flats and small homes.", "Kandivali East", 0, [("Pest Control", 500)]),
    ("Sameer Qureshi", "9000001020", 8, "RO purifier installation, servicing, and filter changes.", "Goregaon", 1, [("RO Repair", 350), ("Plumbing", 500)]),
]


def main():
    init_db()
    added = updated = 0
    with get_db() as conn:
        for name, phone, years, description, area, verified, services in PROVIDERS:
            email = "mock." + phone + "@fixmate.demo"
            user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if user:
                user_id = user["id"]
                conn.execute(
                    "UPDATE users SET name = ?, phone = ?, role = 'PROVIDER' WHERE id = ?",
                    (name, phone, user_id),
                )
                updated += 1
            else:
                cur = conn.execute(
                    "INSERT INTO users (name, email, phone, password_hash, role) VALUES (?, ?, ?, ?, 'PROVIDER')",
                    (name, email, phone, generate_password_hash(PASSWORD)),
                )
                user_id = cur.lastrowid
                added += 1

            profile = conn.execute(
                "SELECT id FROM provider_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
            if profile:
                provider_id = profile["id"]
                conn.execute(
                    "UPDATE provider_profiles SET experience_years = ?, description = ?, service_area = ?, verified = ? WHERE id = ?",
                    (years, description, area, verified, provider_id),
                )
            else:
                cur = conn.execute(
                    "INSERT INTO provider_profiles (user_id, experience_years, description, service_area, verified) VALUES (?, ?, ?, ?, ?)",
                    (user_id, years, description, area, verified),
                )
                provider_id = cur.lastrowid

            for category, price in services:
                conn.execute(
                    "INSERT INTO provider_services (provider_id, category, price) VALUES (?, ?, ?) "
                    "ON CONFLICT(provider_id, category) DO UPDATE SET price = excluded.price",
                    (provider_id, category, price),
                )
    print(f"Done. Added {added} mock providers; refreshed {updated} existing mock providers.")
    print("Your consumer account and existing requests/bookings/reviews were not changed.")
    print(f"Demo provider login password (if needed): {PASSWORD}")
    print("Mock emails follow: mock.9000001001@fixmate.demo")


if __name__ == "__main__":
    main()
