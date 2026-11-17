"""Set current IPL team for the supplied IPL 2027 rosters.

Matches roster names to the derived player index, skips players that are not in
the data, and writes only current_team / current_team_type through the status
API so every change lands in the status history.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data_derived" / "player_index.json"

ROSTERS: dict[str, list[str]] = {
    "Chennai Super Kings": [
        "Ruturaj Gaikwad", "Dewald Brevis", "MS Dhoni", "Kartik Sharma",
        "Sarfaraz Khan", "Urvil Patel", "Sanju Samson", "Ayush Mhatre",
        "Aman Khan", "Shivam Dube", "Dian Forrester", "Zak Foulkes",
        "Shreyas Gopal", "Anshul Kamboj", "Macneil Noronha", "Matthew Short",
        "Prashant Veer", "Ramakrishna Ghosh", "Jamie Overton", "Rahul Chahar",
        "Gurjapneet Singh", "Matt Henry", "Akeal Hosein", "Spencer Johnson",
        "Akash Madhwal", "Mukesh Choudhary", "Noor Ahmad", "Kuldip Yadav",
        "Khaleel Ahmed", "Nathan Ellis",
    ],
    "Delhi Capitals": [
        "Abishek Porel", "David Miller", "Karun Nair", "Pathum Nissanka",
        "Sahil Parakh", "KL Rahul", "Nitish Rana", "Prithvi Shaw",
        "Tristan Stubbs", "Ben Duckett", "Axar Patel", "Ajay Mandal",
        "Rehan Ahmed", "Sameer Rizvi", "Ashutosh Sharma", "Madhav Tiwari",
        "Auqib Nabi", "Dushmantha Chameera", "Kyle Jamieson", "Kuldeep Yadav",
        "Mukesh Kumar", "T. Natarajan", "Lungi Ngidi", "Vipraj Nigam",
        "Mitchell Starc", "Tripurana Vijay",
    ],
    "Gujarat Titans": [
        "Shubman Gill", "Anuj Rawat", "Jos Buttler", "Connor Esterhuizen",
        "Kumar Kushagra", "Sai Sudharsan", "M. Shahrukh Khan", "Tom Banton",
        "Jason Holder", "Glenn Phillips", "Rashid Khan", "Nishant Sindhu",
        "Manav Suthar", "Rahul Tewatia", "Washington Sundar", "Arshad Khan",
        "Ashok Sharma", "Gurnoor Brar", "Kulwant Khejroliya", "Mohammed Siraj",
        "Prasidh Krishna", "Kagiso Rabada", "Sai Kishore", "Ishant Sharma",
        "Luke Wood", "Jayant Yadav", "Prithvi Raj",
    ],
    "Kolkata Knight Riders": [
        "Ajinkya Rahane", "Rinku Singh", "Finn Allen", "Tejasvi Dahiya",
        "Manish Pandey", "Rovman Powell", "Angkrish Raghuvanshi",
        "Ramandeep Singh", "Sarthak Ranjan", "Tim Seifert", "Luvnith Sisodia",
        "Rahul Tripathi", "Daksh Kamra", "Cameron Green", "Sunil Narine",
        "Anukul Roy", "Rachin Ravindra", "Vaibhav Arora", "Saurabh Dubey",
        "Kartik Tyagi", "Blessing Muzarabani", "Navdeep Saini",
        "Prashant Solanki", "Umran Malik", "Varun Chakravarthy", "Akash Deep",
        "Harshit Rana", "Mustafizur Rahman", "Matheesha Pathirana",
    ],
    "Lucknow Super Giants": [
        "Rishabh Pant", "Abdul Samad", "Akshat Raghuwanshi",
        "Matthew Breetzke", "Mukul Choudhary", "Himmat Singh", "Josh Inglis",
        "Aiden Markram", "Mitchell Marsh", "Nicholas Pooran", "Ayush Badoni",
        "Arshin Kulkarni", "George Linde", "Shahbaz Ahmed", "Wanindu Hasaranga",
        "Akash Singh", "Avesh Khan", "Mohammed Shami", "Mohsin Khan",
        "Anrich Nortje", "Prince Yadav", "Digvesh Rathi",
        "Manimaran Siddharth", "Arjun Tendulkar", "Naman Tiwari", "Mayank Yadav",
    ],
    "Mumbai Indians": [
        "Ruchit Ahir", "Danish Malewar", "Robin Minz", "Naman Dhir",
        "Ryan Rickelton", "Sherfane Rutherford", "Rohit Sharma",
        "Suryakumar Yadav", "Quinton de Kock", "Hardik Pandya",
        "Corbin Bosch", "Will Jacks", "Mahipal Lomror", "Mayank Rawat",
        "Shardul Thakur", "Tilak Varma", "Atharva Ankolekar", "Raj Bawa",
        "Mitchell Santner", "Ashwani Kumar", "Trent Boult", "Jasprit Bumrah",
        "Deepak Chahar", "AM Ghazanfar", "Krish Bhagat", "Keshav Maharaj",
        "Mayank Markande", "Mohammed Izhar", "Raghu Sharma",
    ],
    "Punjab Kings": [
        "Shreyas Iyer", "Priyansh Arya", "Pyla Avinash", "Harnoor Singh",
        "Prabhsimran Singh", "Vishnu Vinod", "Nehal Wadhera",
        "Azmatullah Omarzai", "Cooper Connolly", "Marco Jansen",
        "Musheer Khan", "Mitchell Owen", "Shashank Singh", "Marcus Stoinis",
        "Suryansh Shedge", "Arshdeep Singh", "Xavier Bartlett",
        "Yuzvendra Chahal", "Praveen Dubey", "Ben Dwarshuis",
        "Lockie Ferguson", "Harpreet Brar", "Vishal Nishad",
        "Vijaykumar Vyshak", "Yash Thakur",
    ],
    "Rajasthan Royals": [
        "Riyan Parag", "Aman Rao", "Shubham Dubey", "Shimron Hetmyer",
        "Yashasvi Jaiswal", "Dhruv Jurel", "Lhuan-dre Pretorius",
        "Vaibhav Sooryavanshi", "Ravi Singh", "Emanjot Singh Chahal",
        "Donovan Ferreira", "Ravindra Jadeja", "Dasun Shanaka", "Sam Curran",
        "Jofra Archer", "Brijesh Sharma", "Nandre Burger", "Tushar Deshpande",
        "Kwena Maphaka", "Adam Milne", "Sushant Mishra", "Vignesh Puthur",
        "Ravi Bishnoi", "Sandeep Sharma", "Kuldeep Sen", "Yash Raj Punja",
        "Yudhvir Singh",
    ],
    "Royal Challengers Bengaluru": [
        "Rajat Patidar", "Jordan Cox", "Tim David", "Virat Kohli",
        "Devdutt Padikkal", "Phil Salt", "Jitesh Sharma", "Jacob Bethell",
        "Kanishk Chouhan", "Venkatesh Iyer", "Vihaan Malhotra",
        "Mangesh Yadav", "Krunal Pandya", "Romario Shepherd",
        "Abhinandan Singh", "Satvik Deswal", "Jacob Duffy",
        "Richard Gleeson", "Josh Hazlewood", "Bhuvneshwar Kumar",
        "Vicky Ostwal", "Rasikh Salam", "Suyash Sharma", "Swapnil Singh",
        "Nuwan Thushara", "Yash Dayal",
    ],
    "Sunrisers Hyderabad": [
        "Salil Arora", "Travis Head", "Ishan Kishan", "Heinrich Klaasen",
        "Ravichandran Smaran", "Aniket Verma", "Abhishek Sharma",
        "RS Ambrish", "Harsh Dubey", "Krains Fuletra", "Liam Livingstone",
        "Kamindu Mendis", "Nitish Kumar Reddy", "Harshal Patel",
        "Shivang Kumar", "Brydon Carse", "Jack Edwards", "Shivam Mavi",
        "Pat Cummins", "Amit Kumar", "Gerald Coetzee", "Praful Hinge",
        "Dilshan Madushanka", "Eshan Malinga", "Sakib Hussain",
        "Onkar Tarmale", "Jaydev Unadkat", "Zeeshan Ansari", "David Payne",
    ],
}

ALIASES = {
    "MS Dhoni": "Mahendra Singh Dhoni",
    "Zak Foulkes": "Zakary Foulkes",
    "KL Rahul": "Lokesh Rahul",
    "Nishant Sindhu": "Nishant Kumar Sindhu",
    "Will Jacks": "William Jacks",
    "Tilak Varma": "Namboori Tilak Varma",
    "AM Ghazanfar": "Allah Ghazanfar",
    "Lhuan-dre Pretorius": "Lhuan Pretorius",
    "Yash Raj Punja": "Yash Punja",
    "Nitish Kumar Reddy": "Nitish Reddy",
    "Pat Cummins": "Patrick Cummins",
    "Vijaykumar Vyshak": "Vyshak Kumar",
}


def _norm(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    return re.sub(r"\b([a-z])\b(?=\s)", r"\1", key)


def load_names() -> dict[str, list[str]]:
    entries = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    names: dict[str, list[str]] = {}
    for entry in entries:
        names.setdefault(_norm(entry["name"]), []).append(entry["name"])
    return names


def resolve(name: str, by_norm: dict[str, list[str]]) -> str | None:
    if name in ALIASES:
        return ALIASES[name]
    hits = set(by_norm.get(_norm(name), []))
    return hits.pop() if len(hits) == 1 else None


def plan(by_norm: dict[str, list[str]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    matched: dict[str, list[str]] = {}
    missing: dict[str, list[str]] = {}
    for team, players in ROSTERS.items():
        resolved = []
        for raw in players:
            hit = resolve(raw, by_norm)
            if hit is None:
                missing.setdefault(team, []).append(raw)
            else:
                resolved.append(hit)
        matched[team] = resolved
    return matched, missing


def post_bulk(api: str, names: list[str], team: str) -> dict:
    body = json.dumps(
        {"names": names, "current_team": team, "current_team_type": "ipl"}
    ).encode("utf-8")
    request = urllib.request.Request(
        api.rstrip("/") + "/api/status/bulk",
        data=body,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    matched, missing = plan(load_names())
    total_matched = sum(len(v) for v in matched.values())
    total_players = sum(len(v) for v in ROSTERS.values())

    for team, players in matched.items():
        print(f"{team}: {len(players)}/{len(ROSTERS[team])} matched")
        if missing.get(team):
            print("  not in data: " + ", ".join(missing[team]))
    print(f"\nTotal matched: {total_matched}/{total_players}")

    if args.dry_run:
        return 0

    changed_total = 0
    for team, names in matched.items():
        if not names:
            continue
        result = post_bulk(args.api, names, team)
        changed_total += result.get("changed", 0)
        print(f"  wrote {team}: {result.get('changed', 0)} changed")
    print(f"\nUpdated {changed_total} players. Unmatched players left untouched.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"Could not reach the status API: {exc}")
        raise SystemExit(1)
