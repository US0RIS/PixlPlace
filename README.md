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
