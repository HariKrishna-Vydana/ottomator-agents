import email.utils

# List of email strings
emails = [
    "John Doe <john.doe@example.com>",
    "jane_doe@example.com",
    "admin@website.org",
    "user123 <user123@domain.com>",
    "Alice Bob <alice.bob@sub.domain.com>",
    "no-reply@my-site.com",
    "support@company.co.uk",
    "contact@mywebsite.org",
    "testuser@localhost",
    "invalid-email-address"
]

# Parsing each email and displaying the result
for email_str in emails:
    name, addr = email.utils.parseaddr(email_str)
    print(f"Input: {email_str}")
    print(f"Parsed Name: {name}")
    print(f"Parsed Address: {addr}")
    print("----")
