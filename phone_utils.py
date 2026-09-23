"""
Phone number utilities: E.164 normalization + basic landline/toll-free
detection.

IMPORTANT LIMITATION: landline/toll-free detection here is a free heuristic,
not a definitive check. It catches the obvious cases (US toll-free
prefixes, Indian numbers that don't start with a mobile digit) but cannot
reliably tell mobile vs landline for most countries — phone numbering plans
don't encode that information predictably everywhere. For a production
system sending real SMS/WhatsApp at volume, use a paid lookup service
(e.g. Twilio Lookup API, ~$0.005/lookup) for accurate line-type detection
before sending. This heuristic is meant to catch clear no-go cases cheaply,
not to replace a real lookup.
"""
import re

US_TOLL_FREE_PREFIXES = {"800", "888", "877", "866", "855", "844", "833", "822"}


def normalize_to_e164(raw_phone: str, default_country_code: str = "+1") -> str | None:
    """
    Convert a loosely-formatted phone number to E.164 (+<countrycode><number>,
    digits only after the +). Returns None if the input doesn't contain
    enough digits to be a plausible phone number.

    Examples:
        normalize_to_e164("(302) 219-0702")              -> "+13022190702"
        normalize_to_e164("+91 129-2251300")               -> "+911292251300"
        normalize_to_e164("(928) 782-3823 Ext. 154")       -> "+19287823823"  (extension dropped)
        normalize_to_e164("919876543210", "+91")            -> "+919876543210"
    """
    if not raw_phone:
        return None

    # Drop anything after "ext"/"x" (extensions aren't part of the dialable E.164 number)
    raw_phone = re.split(r"\b(ext|x)\b", raw_phone, flags=re.IGNORECASE)[0]

    had_plus = raw_phone.strip().startswith("+")
    digits = re.sub(r"\D", "", raw_phone)  # strip everything except digits

    if len(digits) < 7:
        return None  # too short to plausibly be a phone number

    if had_plus:
        return f"+{digits}"

    # No leading '+' in the input — assume it needs the default country code,
    # UNLESS it already looks like it includes one (e.g. a 12-digit number
    # starting with "91" for India, or 11 digits starting with "1" for US/Canada).
    if default_country_code == "+91" and len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if default_country_code == "+1" and len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"

    # Otherwise, take the last 10 digits (typical national number length for
    # both US and India) and prefix with the default country code.
    national_number = digits[-10:]
    return f"{default_country_code}{national_number}"


def is_likely_unreachable_for_sms_whatsapp(e164_phone: str) -> tuple[bool, str]:
    """
    Heuristic check for numbers that are unlikely to receive SMS/WhatsApp
    (toll-free lines, or non-mobile-looking numbers). Returns
    (is_likely_unreachable, reason). This is a best-effort free check —
    see module docstring for limitations.
    """
    if not e164_phone or not e164_phone.startswith("+"):
        return True, "Not a valid E.164 number"

    digits = e164_phone[1:]

    # --- US/Canada (+1) ---
    if digits.startswith("1") and len(digits) == 11:
        area_code = digits[1:4]
        if area_code in US_TOLL_FREE_PREFIXES:
            return True, f"US toll-free number ({area_code}) — cannot receive SMS/WhatsApp"
        # Can't reliably distinguish US mobile vs landline from the number alone —
        # US numbering plan doesn't encode this. Assume reachable; a real lookup
        # (Twilio Lookup API) is needed for certainty.
        return False, "Assumed reachable (US mobile/landline not distinguishable without a lookup API)"

    # --- India (+91) ---
    if digits.startswith("91") and len(digits) == 12:
        national = digits[2:]
        if len(national) == 10 and national[0] in "6789":
            return False, "Looks like an Indian mobile number"
        else:
            return True, "Does not match Indian mobile number pattern (likely a landline/STD number)"

    # --- Other countries: no heuristic available ---
    return False, "Assumed reachable (no heuristic available for this country code)"


if __name__ == "__main__":
    # Quick self-test with the numbers from the Hetvi leads screenshot
    test_numbers = [
        ("(302) 219-0702", "+1"),
        ("(888) 477-9540", "+1"),
        ("+91 129-2251300", "+91"),
        ("(928) 782-3823 Ext. 154", "+1"),
        ("360-757-4433", "+1"),
    ]
    for raw, default_cc in test_numbers:
        e164 = normalize_to_e164(raw, default_cc)
        unreachable, reason = is_likely_unreachable_for_sms_whatsapp(e164) if e164 else (True, "Could not normalize")
        print(f"{raw!r:35} -> {e164!r:20} | unreachable={unreachable} | {reason}")
