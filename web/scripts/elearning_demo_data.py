"""Fixed development catalog. No runtime imports or lesson content blocks."""
MARKER = "[Development seed: madar-elearning-demo-v1]"
COURSES = [
    ("english", "English Communication", "published", "paid", "Build confidence in everyday, travel, and workplace conversations.", [
        ("Getting Started", ["Introducing Yourself", "Greetings and Farewells", "Asking Simple Questions", "Everyday Expressions", "Numbers and Dates", "Talking About Family", "Describing Your Routine", "Listening for Key Information"]),
        ("Daily Communication", ["Making Small Talk", "Ordering Food", "Shopping Conversations", "Giving Directions", "Making Appointments", "Expressing Preferences", "Asking for Help", "Handling Misunderstandings"]),
        ("Travel English", ["At the Airport", "Checking Into a Hotel", "Using Public Transport", "Planning an Itinerary", "Exploring Local Attractions", "Travel Emergencies", "Booking Activities", "Sharing Travel Experiences"]),
        ("Workplace English", ["Introducing Your Role", "Writing Clear Emails", "Joining Team Meetings", "Making Professional Requests", "Discussing Deadlines", "Giving Project Updates", "Customer Conversations", "Resolving Workplace Problems"]),
        ("Confident Speaking", ["Organizing Your Ideas", "Speaking With Clear Pronunciation", "Expressing Opinions", "Agreeing and Disagreeing", "Telling a Story", "Presenting to a Group", "Answering Follow-up Questions", "Planning Your Speaking Practice"]),
    ], 22),
    ("marketing", "Digital Marketing Basics", "published", "free", "Plan practical campaigns, understand audiences, and measure results.", [
        ("Marketing Foundations", ["Understanding Digital Channels", "Defining Your Audience", "Customer Journey Mapping", "Setting Campaign Goals", "Building a Value Proposition", "Creating a Marketing Plan"]),
        ("Content and Social Media", ["Developing a Content Calendar", "Writing Engaging Headlines", "Choosing Social Platforms", "Community Management", "Creating Visual Stories", "Measuring Engagement"]),
        ("Search and Email", ["Keyword Research", "On-page SEO Essentials", "Search Advertising Basics", "Growing an Email List", "Writing Email Campaigns", "Testing Subject Lines"]),
        ("Analytics and Optimization", ["Choosing Useful Metrics", "Reading Campaign Reports", "Tracking Conversions", "Understanding Attribution", "Running A/B Tests", "Improving Campaign Performance"]),
    ], 18),
    ("safety", "Workplace Safety Training", "published", "private", "Recognize hazards, prevent incidents, and respond confidently to emergencies.", [
        ("Safety Fundamentals", ["Recognizing Workplace Hazards", "Understanding Safety Responsibilities", "Reporting Near Misses", "Using Personal Protective Equipment", "Completing a Risk Assessment"]),
        ("Safe Working Practices", ["Manual Handling Techniques", "Ergonomics at Your Workstation", "Electrical Safety Basics", "Working With Chemicals", "Preventing Slips and Trips"]),
        ("Emergency Preparedness", ["Responding to a Fire Alarm", "Evacuation Procedures", "First Aid Awareness", "Communicating During Emergencies", "Learning From Incident Reviews"]),
    ], 12),
    ("leadership", "Leadership Fundamentals", "draft", "paid", "Practice thoughtful decisions, coaching, and collaborative team leadership.", [
        ("Knowing Yourself", ["Understanding Your Leadership Style", "Identifying Personal Values", "Building Self-awareness", "Managing Your Energy", "Creating a Development Plan"]),
        ("Leading a Team", ["Setting Clear Expectations", "Building Psychological Safety", "Delegating With Confidence", "Giving Constructive Feedback", "Recognizing Team Contributions"]),
        ("Communication and Coaching", ["Practicing Active Listening", "Asking Coaching Questions", "Handling Difficult Conversations", "Supporting Individual Growth", "Facilitating Productive Meetings"]),
        ("Decisions and Change", ["Making Ethical Decisions", "Prioritizing Under Pressure", "Leading Through Uncertainty", "Managing Resistance to Change", "Reflecting on Leadership Impact"]),
    ], 0),
]
PROGRESS_TARGETS = (0, 10, 25, 40, 50, 65, 75, 90, 100)
