# Rhythm Habit Tracker — Product Requirements

## Problem statement
Build a mobile-first habit tracker where one Dashboard contains independent monthly progress calendars stacked vertically. Users should see each habit's progress, tap any day to update it directly, feel motivated by accumulating green cells, create habits, reorder cards, sign in with Google or email/password, and switch between device-following light/dark themes.

## Architecture
- Expo SDK 54 / React Native frontend with Expo Router, secure mobile sessions, AsyncStorage for theme preference, Reanimated/Gesture Handler for tactile card gestures, and Safe Area Insets.
- FastAPI backend on `/api` with MongoDB persistence for users, sessions, habits, and daily entries.
- Custom bearer sessions for email/password and Emergent-managed Google OAuth session exchange.
- Per-user habit ordering, per-habit month state, boolean completion records, and measurable values persisted through the API.

## User personas
- **The visual progress seeker:** wants to open the app and immediately see a month becoming greener.
- **The flexible tracker:** records both simple yes/no practices and measurable goals such as water, exercise, or reading.
- **The organized planner:** creates, reorders, and reviews several habits without losing each habit's individual context.

## Core requirements (static)
- One vertically scrollable Dashboard with independent habit cards.
- Month-first GitHub-style calendar for every habit, with per-day tap interaction.
- Yes/no day completion and clear behavior; measurable value entry with green intensity.
- Target, unit, streak, completion count, percentage, month navigation, add habit, and reorder.
- Google sign-in plus email/password account creation and login.
- Device-following light/dark theme with an in-app toggle.
- Touch-safe responsive layouts for compact mobile screens.

## Implemented (2026-08-30)
- Built authenticated Rhythm experience with email/password registration/login, secure bearer sessions, `/auth/me`, and Emergent-managed Google session exchange.
- Built stacked independent habit dashboards with per-card month navigation, GitHub-style calendar cells, accessible status labels, green measurable intensity, streaks, and completion statistics.
- Added direct boolean and measurable day editing, keyboard-safe scrollable entry sheet, add-habit flow with icon/type/target/unit, theme toggle, pull-to-refresh behavior, and long-press vertical drag reorder with persistence.
- Added deterministic test IDs, environment-compatible API root fallback, QA credentials record, and backend indexes/projections for user-safe MongoDB responses.
- Verified with backend regression and mobile UI validation through 375x667: login, create/edit/clear entries, measurable green intensity, month navigation, theme toggle, reorder persistence, and no red-screen/runtime errors.
- Added per-habit Month | Week view toggle (Month remains default). Week view shows the current week as a single row of 7 large tappable day cells with prev/next-week navigation and week-scoped completion stats.
- Added per-habit overflow (⋯) menu on each card with Hide and Delete (confirmation). Backend supports `hidden` boolean via PATCH `/api/habits/{id}` and full delete via DELETE `/api/habits/{id}`.
- Replaced dashboard header theme/logout buttons with a single hamburger menu. The Settings sheet groups Appearance (System/Light/Dark), Hidden habits (with per-item Unhide), and Sign out.
- Refreshed Tick It branding with the latest full-color mark. Auth screen shows it as a full-bleed cover from the top of the screen. Dashboard header uses a bigger "Tick It" title with a smaller greeting subtitle.
- Habit cards were tightened: the Month/Week toggle and ⋯ menu sit inline with the habit name. The "Daily practice" subtitle is removed; measurable habits keep a compact target line. Streak moved into the card footer.
- Added a per-habit color picker (7 preset colors) in Add Habit. Color drives the day-cell shades, completion percent, card highlights, and the Unhide chip in Settings. Backend `HabitCreate`/`HabitUpdate` accept `color`.
- Fixed the ⋯ card menu positioning. It now anchors under the actual card's dots (measured with `measureInWindow`) instead of always appearing at the top.
- Added Edit to the card's ⋯ menu. Edit lets users change name, icon, color, and (for measurable habits) target/unit. Type is locked and cannot be changed after creation. Backend PATCH `/api/habits/{id}` accepts partial updates.
- Today's date box now has a distinct 2px dark border across all cards so the current day is immediately spottable in month and week views.

## Prioritized backlog
- **P0:** None remaining for the requested MVP.
- **P1:** Add richer celebration/confetti particles on successful completions; optionally add Google profile image rendering.
- **P2:** Habit editing/archive, reminder notifications, streak history insights, export/shareable monthly progress, and accessibility settings for reduced motion.

## Next task list
1. Validate product behavior with real user habits beyond the QA account.
2. Add Week View only after the Month View interaction feels complete.
3. Add reminder scheduling and shareable green-month summaries as the first retention and shareability enhancement.