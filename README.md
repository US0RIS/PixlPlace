# PixlPlace

# Pixel Canvas - Phase 1: Core Engine

## What's Implemented

### Database Schema
- **Users**: id, username, credits, lifetime_paid_placements
- **Pixels**: x, y, color, cost_level, owner_id, is_ad, updated_at
- **Placements**: Complete transaction log
- **Global State**: week_start, last_placement, current_cap

### Core Features
1. **Atomic Pixel Placement**: Transaction-safe placement with:
   - Credit validation and deduction
   - Cost calculation based on pixel history
   - Cost level incrementing
   - Dynamic price cap logic

2. **Weekly Reset**: 
   - Auto-detects week boundaries
   - Resets all cost_levels to 0
   - Resets price cap to $2

3. **Free Placement Rules**:
   - **Inactivity Free Mode**: After 30min of no activity, eligible users (≤500 paid placements) place for free
   - **End of Week Free**: Last 5000 placements approximation for eligible users

4. **Dynamic Price Cap**:
   - Starts at $2 (200,000 credits)
   - Drops to $1.50 when 100 pixels reach cap
   - Resets weekly

5. **Rate Limiting**:
   - 1 second minimum between placements per user
   - Prevents rapid-fire abuse

### API Endpoints

#### `GET /board`
Returns all pixels with metadata.

#### `POST /place`
```json
{
  "user_id": 1,
  "x": 512,
  "y": 512,
  "color": "#FF0000",
  "is_ad": false
}
```

Returns cost, whether free, new balance.

#### `POST /user/create`
Create test users with initial credits.

#### `GET /user/{user_id}`
Get user info and balance.

#### `GET /stats`
Global statistics (cap, placements, etc).

## Running

```bash
pip install -r requirements.txt
python main.py
```

API runs on http://localhost:8000

Docs at http://localhost:8000/docs

## Testing Flow

1. Create a user with credits:
   ```
   POST /user/create?username=test1&initial_credits=500000
   ```

2. Place a pixel:
   ```
   POST /place
   {
     "user_id": 1,
     "x": 100,
     "y": 100,
     "color": "#FF0000",
     "is_ad": false
   }
   ```

3. View board:
   ```
   GET /board
   ```

4. Check stats:
   ```
   GET /stats
   ```

## What's NOT in Phase 1
- UI (HTML/CSS/JS)
- Undo functionality
- Ad penalties/moderation
- Reporting/freeze mechanism
- Archives
- Leaderboards
- Stripe integration

## Database File
SQLite database: `pixelcanvas.db` (auto-created)

## Notes
- All costs in credits (10 credits = $0.01)
- Base cost: 1000 credits ($0.10)
- Cost increment: 1000 credits per level ($0.10)
- Transactions are atomic via SQLite IMMEDIATE isolation
- Rate limiting uses in-memory dict (will reset on restart)

# Pixel Canvas - Phase 2: Basic UI

## What's New in Phase 2

### Landing Page (`/`)
- **Canvas-first design** with live board preview
- **Grid brutalism aesthetic** with neon accents
- **Animated background** grid
- **Live stats display** showing:
  - Total pixels placed
  - This week's placements  
  - Current price cap
- **Smooth animations** and glitch effects
- Auto-refreshing board preview (30s intervals)

### Canvas Page (`/canvas.html`)
- **Interactive pixel canvas** with:
  - Zoom controls (mousewheel, +/- buttons)
  - Pan controls (middle-click or shift+drag)
  - Pixel-perfect rendering
  - Grid overlay when zoomed in
- **Color picker** with:
  - 16 preset colors
  - Custom color selector
  - Visual selection indicators
- **Pixel hover info** showing:
  - Position (x, y)
  - Current color
  - Placement cost
  - Owner ID
  - Ad status
- **Placement interface**:
  - "Mark as Advertisement" checkbox
  - Real-time credit balance
  - One-click placement
  - Rate limit handling
- **Live notifications** for:
  - Successful placements
  - Errors (insufficient credits, rate limits)
  - Network issues
- **Mock login system** (demo for Phase 2)

### Design Features
- **Retro arcade aesthetic** using Press Start 2P font
- **Cyberpunk color palette**: cyan, pink, yellow accents on dark bg
- **Smooth animations**: hover states, button interactions, notifications
- **Responsive layout** (mobile-friendly)
- **Pixelated rendering** for authentic pixel art look

### Placeholder Pages
- `/leaderboards.html` - Coming in Phase 4
- `/archives.html` - Coming in Phase 4

## File Structure

```
/
├── main.py (updated with static file serving)
├── static/
│   ├── index.html (landing page)
│   ├── canvas.html (interactive canvas)
│   ├── leaderboards.html (placeholder)
│   └── archives.html (placeholder)
└── pixelcanvas.db (database)
```

## Running Phase 2

1. Start the server:
   ```bash
   python main.py
   ```

2. Open browser to: `http://localhost:5000/`

3. Navigate:
   - Landing page shows live board preview
   - Click canvas preview or "Enter Canvas" button
   - Click "Login" to create demo user (gets 500k credits)
   - Select color, hover over pixels, click to place

## What Works

✓ Landing page with live board preview
✓ Interactive canvas with zoom/pan
✓ Color picker (presets + custom)
✓ Hover info showing pixel details
✓ Placement with real-time updates
✓ Credit tracking
✓ Rate limiting feedback
✓ Cost calculation display
✓ Ad checkbox
✓ Notifications for success/error
✓ Auto-refresh (board updates every 10s in canvas)

## What's NOT in Phase 2

- Real authentication (using mock login)
- Undo functionality
- Ad penalties/saturation
- Reporting system
- Leaderboards
- Archives
- Stripe integration

## Testing Phase 2

1. Open homepage - see live board preview
2. Click "Login" - enter any username
3. Click "Enter Canvas"
4. Use mouse wheel to zoom
5. Shift+drag or middle-click to pan
6. Hover over pixels to see info
7. Click to select position
8. Choose color
9. Click "Place Pixel"
10. Watch credits deduct and pixel appear

## Next: Phase 3

Phase 3 will add:
- Undo functionality
- Ad labeling enforcement
- Dynamic price cap logic
- Reporting + freeze mechanism

# Pixel Canvas - Phase 3: Advanced Rules

## What's New in Phase 3

### 1. UNDO System ⏪
- **Time Window**: 5 minutes to undo after placement
- **Cost**: 25% of original placement cost
- **Escalation**: Each undo increases the next undo cost by +10% of original
- **Reset**: Escalation counter resets weekly
- **Not a Refund**: Undo costs credits, doesn't refund them
- **UI**: Yellow "Undo Last Placement" button appears after placing
- **Auto-disable**: Button disables after 5 minutes

### 2. Ad Labeling & Penalties 📢
- **Visual Effect**: Ad pixels appear 50% less saturated (visual not yet implemented in UI)
- **Overwrite Discount**: Ads are 10% cheaper to overwrite
- **Violation Tracking**: Users who mislabel ads get tracked (penalties TBD)
- **Database**: `ad_violation_count` field added to users table

### 3. Dynamic Price Cap (Enhanced) 💰
- Already implemented in Phase 1, now verified working:
  - Starts at $2.00 per pixel
  - Drops to $1.50 when 100 pixels reach cap
  - Resets weekly

### 4. Reporting & Freeze System 🚨
- **User Reports**: Anyone can report inappropriate pixels
- **Threshold**: 2,500 reports in a week triggers board freeze
- **Freeze**: No new placements allowed until weekly reset
- **UI**: Pink "Report Pixel" button in sidebar
- **Stats**: Report count visible in `/stats` endpoint

## Database Changes

### Updated Tables:

**users** - Added:
- `undo_escalation_count` (tracks undo usage)
- `ad_violation_count` (tracks ad mislabeling)

**placements** - Added:
- `can_undo` (whether placement can still be undone)
- `previous_color` (for restoring on undo)
- `previous_owner_id` (for restoring on undo)

**New Table: reports**
- `reporter_user_id`
- `pixel_x`, `pixel_y`
- `reason`
- `reported_at`

**global_state** - Added:
- `board_frozen` (whether board accepts placements)

## New API Endpoints

### `POST /undo/{placement_id}?user_id={user_id}`
Undo a recent placement.

**Response:**
```json
{
  "success": true,
  "undo_cost": 250,
  "new_balance": 499750,
  "message": "Placement undone (cost: 250 credits)"
}
```

**Errors:**
- 403: Not your placement / Board frozen
- 400: Undo window expired / Cannot undo
- 402: Insufficient credits
- 404: Placement not found

### `POST /report?user_id={user_id}&x={x}&y={y}&reason={reason}`
Report a pixel for inappropriate content.

**Response:**
```json
{
  "success": true,
  "message": "Report submitted",
  "board_frozen": false,
  "report_count": 1542
}
```

If threshold reached:
```json
{
  "success": true,
  "message": "Report submitted. Board frozen (2501 reports this week)",
  "board_frozen": true,
  "report_count": 2501
}
```

### Updated `/stats` Endpoint
Now includes:
```json
{
  "board_frozen": false,
  "reports_this_week": 1542,
  "report_threshold": 2500
}
```

## UI Changes

### Canvas Page Updates:
1. **Undo Button** (yellow)
   - Appears after pixel placement
   - Shows for 5 minutes
   - Displays undo cost on use
   
2. **Report Button** (pink outline)
   - Enabled when pixel selected and logged in
   - Prompts for optional reason
   - Shows current report count

3. **Visual Feedback**
   - Success/error notifications for all actions
   - Credit balance updates in real-time
   - Board state reflected immediately

## Weekly Reset Enhanced

The weekly reset now:
1. Resets pixel cost levels to 0
2. Resets price cap to $2.00
3. **NEW:** Resets undo escalation for all users
4. **NEW:** Unfreezes the board
5. **NEW:** Clears report history (implicitly - reports older than week_start are ignored)

## Testing Phase 3

### Test Undo:
1. Login with test user
2. Place a pixel (costs 1000 credits)
3. Click "Undo Last Placement" within 5 minutes
4. Should cost 250 credits (25%)
5. Place another pixel, undo again
6. Second undo should cost 350 credits (25% + 10%)

### Test Reporting:
1. Login and select any pixel
2. Click "Report Pixel"
3. Enter optional reason
4. Check `/stats` endpoint - report_count should increase
5. (To test freeze, would need to submit 2,500 reports)

### Test Ad Discount:
1. Place a pixel marked as "Advertisement"
2. Try to overwrite it
3. Cost should be ~10% less than normal

### Test Board Freeze:
1. Submit 2,500+ reports (can do programmatically via API)
2. Try to place a pixel
3. Should get 403 error: "Board is frozen"
4. Trigger weekly reset (or wait)
5. Board unfreezes automatically

## What's NOT in Phase 3

- Visual saturation effect for ads (CSS filter needed)
- Ad verification/moderation system
- Penalties for repeat ad violations
- Leaderboards (Phase 4)
- Archives (Phase 4)
- Stripe integration (future)

## Phase 3 Complete ✅

All advanced rules implemented:
- ✅ Undo with escalating costs
- ✅ Ad labeling with overwrite discount
- ✅ Dynamic price cap (from Phase 1)
- ✅ Reporting with freeze threshold
- ✅ Weekly resets include all new features

**Next: Phase 4** will add Archives & Leaderboards
