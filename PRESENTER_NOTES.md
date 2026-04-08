# Presenter Quick Reference

## Test Messages (Copy & Paste Ready)

### ❌ Test 1: Missing UNB/UNZ (Will Fail)
```
UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+610+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'
```
**Errors**: Missing UNB, Missing UNZ

---

### ❌ Test 2: Invalid BGM Code (Will Fail)
```
UNB+UNOC:3+SENDER:ZZZ+RECEIVER:ZZZ+260408:1200+REF123'UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+999+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'UNZ+1+REF123'
```
**Error**: BGM code '999' invalid (must be 335, 610, or 730)

---

### ❌ Test 3: Reference Mismatch (Will Fail)
```
UNB+UNOC:3+SENDER:ZZZ+RECEIVER:ZZZ+260408:1200+REF123'UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+610+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'UNZ+1+REF999'
```
**Error**: UNB reference (REF123) ≠ UNZ reference (REF999)

---

### ✅ Test 4: Perfect Message (Will Pass)
```
UNB+UNOC:3+SENDER:ZZZ+RECEIVER:ZZZ+260408:1200+REF123'UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+610+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'UNZ+1+REF123'
```
**Result**: ✅ All validations pass

---

## Demo Flow (5 minutes)

1. **Introduction** (30s)
   - "I built an EDI validator for IFTMIN messages"
   - "Validates 11 business rules + structure"

2. **Show Interface** (30s)
   - Point out text area
   - Show Format, Validate, Clear buttons
   - Mention ⚙️ API Settings for network use

3. **Demo #1: Invalid BGM** (1 min)
   - Paste Test 2
   - Click Validate
   - **Point out**: Red border on BGM segment
   - **Show**: 💡 Suggestion box
   - **Explain**: "Invalid code 999, should be 610, 335, or 730"

4. **Demo #2: Missing Segments** (1 min)
   - Clear and paste Test 1
   - Click Validate
   - **Show**: Multiple errors (UNB, UNZ highlighted)
   - **Explain**: "Strict interchange mode requires UNB/UNZ wrapper"

5. **Demo #3: Reference Mismatch** (1 min)
   - Clear and paste Test 3
   - Click Validate
   - **Show**: UNZ segment highlighted
   - **Read suggestion**: "UNB and UNZ must have matching references"

6. **Demo #4: Successful Validation** (1 min)
   - Clear and paste Test 4
   - Click Validate
   - **Show**: Green ✅ "Validation passed"
   - **Explain**: "All 11 rules validated"

7. **Extra Features** (1 min)
   - Click **Format** (show segment splitting)
   - Show **syntax coloring** (blue UNH, green BGM, etc.)
   - Mention **227 passing tests**

8. **Questions & Setup** (30s)
   - GitHub link available
   - Can run on local network
   - Python + FastAPI backend

---

## Key Talking Points

✅ "Validates **11 critical business rules** for Bring's IFTMIN implementation"  
✅ "**Real-time visual feedback** - errors highlighted in red directly in the editor"  
✅ "**Smart suggestions** - not just errors, but how to fix them"  
✅ "**Two modes**: Client-side JavaScript or server-side Python API"  
✅ "**Battle-tested**: 227 automated tests, all passing"  
✅ "**Open Source**: Available on GitHub for team use"

---

## Technical Q&A Prep

**Q: What technology stack?**  
A: Python 3.13 backend (FastAPI), vanilla JavaScript frontend, no frameworks needed

**Q: Can it validate other message types?**  
A: Currently IFTMIN only, but parser is extensible for other UN/EDIFACT types

**Q: How do you handle escape sequences?**  
A: Custom "split-without-decode" algorithm handles ??, ?', ?+ correctly

**Q: What about segment groups?**  
A: Validates hierarchy, order, and max occurrences (SG11, SG18, SG32)

**Q: Performance?**  
A: Instant client-side, <100ms server-side

**Q: Can we customize rules?**  
A: Yes! Edit `bring_rules.json` for segments, qualifiers, etc.

---

## Network Setup Checklist

- [ ] `START_SERVER_NETWORK.bat` is running
- [ ] Firewall allows port 8000
- [ ] Test from your own browser first
- [ ] Note your IP: `192.168.1.4`
- [ ] Colleagues have `index.html` file
- [ ] They've updated API URL to your IP

---

## Troubleshooting During Demo

**If API fails:**
- Check server terminal for errors
- Restart `START_SERVER_NETWORK.bat`
- Verify firewall isn't blocking

**If highlighting doesn't work:**
- Hard refresh browser (Ctrl+F5)
- Clear browser cache
- Check browser console (F12) for errors

**If validation seems wrong:**
- Double-check message format
- Ensure segments end with `'`
- Try Format button first

---

## Follow-up Resources

📧 **Email after demo:**
- GitHub link: https://github.com/prajaktawanjari/EDI-Validator
- SHARING_GUIDE.md (detailed instructions)
- README.md (full documentation)

💬 **Slack/Teams message:**
```
🎉 EDI Validator is now live!
📦 Download: https://github.com/prajaktawanjari/EDI-Validator
📖 Setup Guide: See SHARING_GUIDE.md in the repo
🆘 Questions? DM me!
```
