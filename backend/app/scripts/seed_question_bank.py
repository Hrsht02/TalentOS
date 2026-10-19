"""Seed a small global question bank for initial TalentOS demos.

Safe to run repeatedly: existing platform question slugs/prompts are left unchanged.
Run after applying Alembic migrations: python -m app.scripts.seed_question_bank
"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import AptitudeQuestion, CodingQuestion, TestCase


APTITUDE_QUESTIONS = [
    {
        "category": "Quantitative Aptitude", "difficulty": "EASY",
        "prompt": "A product costs ₹800 and is discounted by 10%. What is the sale price?",
        "options": [{"id": "A", "text": "₹700"}, {"id": "B", "text": "₹720"}, {"id": "C", "text": "₹740"}, {"id": "D", "text": "₹760"}],
        "answer_key": "B", "explanation": "10% of ₹800 is ₹80; ₹800 − ₹80 = ₹720.",
        "marks": 1.0, "negative_marks": 0.25,
    },
    {
        "category": "Logical Reasoning", "difficulty": "EASY",
        "prompt": "Find the next number in the sequence: 2, 4, 8, 16, ?",
        "options": [{"id": "A", "text": "20"}, {"id": "B", "text": "24"}, {"id": "C", "text": "32"}, {"id": "D", "text": "36"}],
        "answer_key": "C", "explanation": "Each number is twice the previous number.",
        "marks": 1.0, "negative_marks": 0.25,
    },
    {
        "category": "Verbal Ability", "difficulty": "EASY",
        "prompt": "Choose the word closest in meaning to 'concise'.",
        "options": [{"id": "A", "text": "Brief"}, {"id": "B", "text": "Confusing"}, {"id": "C", "text": "Careless"}, {"id": "D", "text": "Uncertain"}],
        "answer_key": "A", "explanation": "Concise means brief while communicating the key information.",
        "marks": 1.0, "negative_marks": 0.25,
    },
    {
        "category": "Quantitative Aptitude", "difficulty": "MEDIUM",
        "prompt": "A team completes 3/5 of a task in 6 days at a constant rate. How many days are needed for the whole task?",
        "options": [{"id": "A", "text": "8"}, {"id": "B", "text": "9"}, {"id": "C", "text": "10"}, {"id": "D", "text": "12"}],
        "answer_key": "C", "explanation": "The full task takes 6 ÷ (3/5) = 10 days.",
        "marks": 2.0, "negative_marks": 0.5,
    },
    {
        "category": "Logical Reasoning", "difficulty": "MEDIUM",
        "prompt": "All developers in a team know Git. Mira is a developer on that team. What follows?",
        "options": [{"id": "A", "text": "Mira knows Git"}, {"id": "B", "text": "Mira manages the team"}, {"id": "C", "text": "Everyone who knows Git is a developer"}, {"id": "D", "text": "No conclusion is possible"}],
        "answer_key": "A", "explanation": "Mira belongs to the group for which Git knowledge is specified.",
        "marks": 2.0, "negative_marks": 0.5,
    },
]

CODING_QUESTIONS = [
    {
        "title": "Sum Two Numbers", "slug": "platform-sum-two-numbers",
        "statement": "Read two integers from standard input and print their sum. The integers may be negative.",
        "constraints_text": "Each integer fits in a signed 32-bit integer.",
        "difficulty": "EASY", "skills": ["programming basics", "input/output"],
        "starter_code": {
            "python": "a, b = map(int, input().split())\nprint(a + b)\n",
            "cpp": "#include <iostream>\nusing namespace std;\nint main(){ long long a,b; cin >> a >> b; cout << a+b << endl; }\n",
            "javascript": "const fs = require('fs');\nconst [a,b] = fs.readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);\nconsole.log(a+b);\n",
        },
        "time_limit_ms": 2000, "memory_limit_mb": 256,
        "tests": [("3 4\n", "7\n"), ("-5 2\n", "-3\n"), ("0 0\n", "0\n")],
    },
    {
        "title": "Reverse a String", "slug": "platform-reverse-string",
        "statement": "Read one line of text and print its characters in reverse order. Preserve spaces in the input line.",
        "constraints_text": "Input contains one line with up to 10000 characters.",
        "difficulty": "EASY", "skills": ["strings", "loops"],
        "starter_code": {
            "python": "text = input()\nprint(text[::-1])\n",
            "cpp": "#include <iostream>\n#include <string>\n#include <algorithm>\nusing namespace std;\nint main(){ string s; getline(cin,s); reverse(s.begin(),s.end()); cout << s << endl; }\n",
            "javascript": "const fs = require('fs');\nconst s = fs.readFileSync(0,'utf8').replace(/\\r?\\n$/, '');\nconsole.log([...s].reverse().join(''));\n",
        },
        "time_limit_ms": 2000, "memory_limit_mb": 256,
        "tests": [("hello\n", "olleh\n"), ("TalentOS\n", "SOt nelaT".replace(" ", "") + "\n"), ("a b\n", "b a\n")],
    },
    {
        "title": "Palindrome Check", "slug": "platform-palindrome-check",
        "statement": "Read one line and print YES if it is a palindrome when compared case-insensitively; otherwise print NO. Ignore spaces at the beginning and end only.",
        "constraints_text": "Input contains one line with up to 10000 characters.",
        "difficulty": "EASY", "skills": ["strings", "two pointers"],
        "starter_code": {
            "python": "s = input().strip().lower()\nprint('YES' if s == s[::-1] else 'NO')\n",
            "cpp": "#include <iostream>\n#include <string>\n#include <algorithm>\nusing namespace std;\nint main(){ string s; getline(cin,s); while(!s.empty() && isspace((unsigned char)s.front())) s.erase(s.begin()); while(!s.empty() && isspace((unsigned char)s.back())) s.pop_back(); transform(s.begin(),s.end(),s.begin(),[](unsigned char c){return tolower(c);}); string r=s; reverse(r.begin(),r.end()); cout << (s==r ? \"YES\" : \"NO\") << endl; }\n",
        },
        "time_limit_ms": 2000, "memory_limit_mb": 256,
        "tests": [("level\n", "YES\n"), ("Hello\n", "NO\n"), ("RaceCar  \n", "YES\n")],
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        added_aptitude = 0
        added_coding = 0
        added_tests = 0
        for data in APTITUDE_QUESTIONS:
            existing = await db.scalar(select(AptitudeQuestion.id).where(
                AptitudeQuestion.owner_company_id.is_(None),
                AptitudeQuestion.prompt == data["prompt"],
            ))
            if existing:
                continue
            db.add(AptitudeQuestion(owner_company_id=None, created_by=None, active=True, **data))
            added_aptitude += 1
        await db.flush()

        for data in CODING_QUESTIONS:
            existing = await db.scalar(select(CodingQuestion).where(CodingQuestion.slug == data["slug"]))
            if existing:
                question = existing
            else:
                fields = {key: value for key, value in data.items() if key != "tests"}
                question = CodingQuestion(owner_company_id=None, created_by=None, active=True, **fields)
                db.add(question)
                await db.flush()
                added_coding += 1
            for position, (input_data, expected_output) in enumerate(data["tests"]):
                test_exists = await db.scalar(select(TestCase.id).where(
                    TestCase.coding_question_id == question.id, TestCase.position == position
                ))
                if not test_exists:
                    db.add(TestCase(coding_question_id=question.id, input_data=input_data,
                                    expected_output=expected_output, hidden=True, weight=1.0,
                                    position=position))
                    added_tests += 1
        await db.commit()
        print(f"Question bank ready: {added_aptitude} aptitude questions, {added_coding} coding questions, {added_tests} test cases added.")


if __name__ == "__main__":
    asyncio.run(seed())
