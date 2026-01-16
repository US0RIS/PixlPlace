from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import sqlite3
import time
from datetime import datetime, timedelta
from contextlib import contextmanager
import threading

app = FastAPI(title="Pixel Canvas API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
BOARD_SIZE = 1024
BASE_COST_CREDITS = 1000  # $0.01 in credits (10 credits = $0.01, so 1000 = $0.10 base)
COST_INCREMENT_CREDITS = 1000  # $0.01 per level
INITIAL_CAP_CREDITS = 200000  # $2.00
LOWER_CAP_CREDITS = 150000  # $1.50
CAP_TRIGGER_COUNT = 100  # pixels at cap before lowering
FREE_WINDOW_SIZE = 5000  # last N placements are free
INACTIVITY_THRESHOLD_SECONDS = 1800  # 30 minutes
FREE_ELIGIBILITY_MAX_PAID = 500  # max paid placements for free eligibility
RATE_LIMIT_SECONDS = 1  # min seconds between placements per user

# In-memory rate limiting
user_last_placement = {}
rate_limit_lock = threading.Lock()

DB_PATH = "pixelcanvas.db"

# Database helper
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, isolation_level="IMMEDIATE")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Initialize database
def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                credits INTEGER DEFAULT 0,
                lifetime_paid_placements INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Pixels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pixels (
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                color TEXT NOT NULL,
                cost_level INTEGER DEFAULT 0,
                owner_id INTEGER,
                is_ad BOOLEAN DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (x, y),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        
        # Placements log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS placements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                color TEXT NOT NULL,
                cost INTEGER NOT NULL,
                was_free BOOLEAN DEFAULT 0,
                is_ad BOOLEAN DEFAULT 0,
                placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Global state
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Initialize global state
        cursor.execute("""
            INSERT OR IGNORE INTO global_state (key, value)
            VALUES ('week_start', datetime('now'))
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO global_state (key, value)
            VALUES ('last_placement', datetime('now'))
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO global_state (key, value)
            VALUES ('current_cap', ?)
        """, (str(INITIAL_CAP_CREDITS),))
        
        conn.commit()

# Request models
class PlacePixelRequest(BaseModel):
    user_id: int
    x: int = Field(..., ge=0, lt=BOARD_SIZE)
    y: int = Field(..., ge=0, lt=BOARD_SIZE)
    color: str = Field(..., pattern="^#[0-9A-Fa-f]{6}$")
    is_ad: bool = False

class BoardResponse(BaseModel):
    width: int
    height: int
    pixels: list

class PlacePixelResponse(BaseModel):
    success: bool
    cost: int
    was_free: bool
    new_balance: int
    message: str

# Helper functions
def get_week_start(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_state WHERE key = 'week_start'")
    row = cursor.fetchone()
    return datetime.fromisoformat(row[0])

def get_last_placement_time(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_state WHERE key = 'last_placement'")
    row = cursor.fetchone()
    return datetime.fromisoformat(row[0])

def get_current_cap(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_state WHERE key = 'current_cap'")
    row = cursor.fetchone()
    return int(row[0])

def check_and_reset_week(conn):
    """Check if a week has passed and reset if needed"""
    week_start = get_week_start(conn)
    now = datetime.now()
    
    if now - week_start >= timedelta(days=7):
        cursor = conn.cursor()
        
        # Reset all pixel cost levels
        cursor.execute("UPDATE pixels SET cost_level = 0")
        
        # Reset week start
        cursor.execute("""
            UPDATE global_state 
            SET value = datetime('now'), updated_at = datetime('now')
            WHERE key = 'week_start'
        """)
        
        # Reset cap
        cursor.execute("""
            UPDATE global_state 
            SET value = ?, updated_at = datetime('now')
            WHERE key = 'current_cap'
        """, (str(INITIAL_CAP_CREDITS),))
        
        conn.commit()
        return True
    return False

def count_week_placements(conn):
    """Count placements this week"""
    week_start = get_week_start(conn)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM placements
        WHERE placed_at >= ?
    """, (week_start.isoformat(),))
    return cursor.fetchone()[0]

def is_free_placement_eligible(conn, user_id):
    """Check if placement should be free"""
    
    # Check inactivity free mode
    last_placement = get_last_placement_time(conn)
    now = datetime.now()
    inactive_seconds = (now - last_placement).total_seconds()
    
    if inactive_seconds >= INACTIVITY_THRESHOLD_SECONDS:
        # Check user's lifetime paid placements
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lifetime_paid_placements FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row and row[0] <= FREE_ELIGIBILITY_MAX_PAID:
            return True, "inactivity"
    
    # Check last 5000 placements
    week_count = count_week_placements(conn)
    week_start = get_week_start(conn)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM placements
        WHERE placed_at >= ? AND placed_at < datetime('now', '-7 days')
    """, (week_start.isoformat(),))
    
    # Simplified: if we're in the last 5000 placements of the week
    # We'll use a simpler heuristic: check total week placements
    # This is approximate but correct for Phase 1
    cursor.execute("""
        SELECT COUNT(*) FROM placements
        WHERE placed_at >= ?
    """, (week_start.isoformat(),))
    total_this_week = cursor.fetchone()[0]
    
    # Estimate end of week
    week_start_dt = get_week_start(conn)
    week_end = week_start_dt + timedelta(days=7)
    time_remaining = (week_end - now).total_seconds()
    
    # If less than certain time remains and user qualifies, could be in free window
    # For now, simplified: last 6 hours of week are free window candidate
    if time_remaining < 21600:  # 6 hours
        cursor.execute("""
            SELECT lifetime_paid_placements FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row and row[0] <= FREE_ELIGIBILITY_MAX_PAID:
            return True, "end_of_week"
    
    return False, None

def calculate_pixel_cost(conn, x, y):
    """Calculate cost to place pixel"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cost_level FROM pixels WHERE x = ? AND y = ?
    """, (x, y))
    row = cursor.fetchone()
    
    cost_level = row[0] if row else 0
    base_cost = BASE_COST_CREDITS
    cost = base_cost + (cost_level * COST_INCREMENT_CREDITS // 1000)
    
    # Apply cap
    current_cap = get_current_cap(conn)
    cost = min(cost, current_cap)
    
    return cost

def update_dynamic_cap(conn):
    """Check if cap should be lowered"""
    current_cap = get_current_cap(conn)
    
    if current_cap == INITIAL_CAP_CREDITS:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM pixels
            WHERE cost_level >= ?
        """, (current_cap // COST_INCREMENT_CREDITS * 1000,))
        
        count = cursor.fetchone()[0]
        
        if count >= CAP_TRIGGER_COUNT:
            cursor.execute("""
                UPDATE global_state
                SET value = ?, updated_at = datetime('now')
                WHERE key = 'current_cap'
            """, (str(LOWER_CAP_CREDITS),))
            conn.commit()

# API Endpoints
@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/")
async def root():
    return {"message": "Pixel Canvas API - Phase 1", "version": "0.1.0"}

@app.get("/board", response_model=BoardResponse)
async def get_board():
    """Get current board state"""
    with get_db() as conn:
        check_and_reset_week(conn)
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT x, y, color, cost_level, owner_id, is_ad, updated_at
            FROM pixels
            ORDER BY x, y
        """)
        
        pixels = []
        for row in cursor.fetchall():
            pixels.append({
                "x": row[0],
                "y": row[1],
                "color": row[2],
                "cost_level": row[3],
                "owner_id": row[4],
                "is_ad": bool(row[5]),
                "updated_at": row[6]
            })
        
        return BoardResponse(
            width=BOARD_SIZE,
            height=BOARD_SIZE,
            pixels=pixels
        )

@app.post("/place", response_model=PlacePixelResponse)
async def place_pixel(request: PlacePixelRequest):
    """Place a pixel on the board"""
    
    # Rate limiting check
    with rate_limit_lock:
        now = time.time()
        last_time = user_last_placement.get(request.user_id, 0)
        
        if now - last_time < RATE_LIMIT_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit: wait {RATE_LIMIT_SECONDS} seconds between placements"
            )
        
        user_last_placement[request.user_id] = now
    
    with get_db() as conn:
        check_and_reset_week(conn)
        cursor = conn.cursor()
        
        # Validate user exists
        cursor.execute("SELECT credits, lifetime_paid_placements FROM users WHERE id = ?", 
                      (request.user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_credits = user_row[0]
        lifetime_paid = user_row[1]
        
        # Check free placement eligibility
        is_free, free_reason = is_free_placement_eligible(conn, request.user_id)
        
        # Calculate cost
        cost = 0 if is_free else calculate_pixel_cost(conn, request.x, request.y)
        
        # Check sufficient credits
        if not is_free and user_credits < cost:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient credits. Need {cost}, have {user_credits}"
            )
        
        # Deduct credits
        if not is_free:
            cursor.execute("""
                UPDATE users
                SET credits = credits - ?,
                    lifetime_paid_placements = lifetime_paid_placements + 1
                WHERE id = ?
            """, (cost, request.user_id))
            
            new_balance = user_credits - cost
        else:
            new_balance = user_credits
        
        # Get current pixel state
        cursor.execute("""
            SELECT cost_level FROM pixels WHERE x = ? AND y = ?
        """, (request.x, request.y))
        
        existing_pixel = cursor.fetchone()
        new_cost_level = (existing_pixel[0] if existing_pixel else 0) + COST_INCREMENT_CREDITS
        
        # Write/update pixel
        cursor.execute("""
            INSERT INTO pixels (x, y, color, cost_level, owner_id, is_ad, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(x, y) DO UPDATE SET
                color = excluded.color,
                cost_level = excluded.cost_level,
                owner_id = excluded.owner_id,
                is_ad = excluded.is_ad,
                updated_at = excluded.updated_at
        """, (request.x, request.y, request.color, new_cost_level, 
              request.user_id, request.is_ad))
        
        # Log placement
        cursor.execute("""
            INSERT INTO placements (user_id, x, y, color, cost, was_free, is_ad, placed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (request.user_id, request.x, request.y, request.color, 
              cost, is_free, request.is_ad))
        
        # Update last placement time
        cursor.execute("""
            UPDATE global_state
            SET value = datetime('now'), updated_at = datetime('now')
            WHERE key = 'last_placement'
        """)
        
        conn.commit()
        
        # Update dynamic cap
        update_dynamic_cap(conn)
        
        message = "Pixel placed"
        if is_free:
            message += f" (free: {free_reason})"
        
        return PlacePixelResponse(
            success=True,
            cost=cost,
            was_free=is_free,
            new_balance=new_balance,
            message=message
        )

@app.get("/user/{user_id}")
async def get_user(user_id: int):
    """Get user information"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, credits, lifetime_paid_placements, created_at
            FROM users WHERE id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user_id,
            "username": row[0],
            "credits": row[1],
            "lifetime_paid_placements": row[2],
            "created_at": row[3]
        }

@app.post("/user/create")
async def create_user(username: str, initial_credits: int = 0):
    """Create a new user (for testing)"""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, credits)
                VALUES (?, ?)
            """, (username, initial_credits))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            return {
                "success": True,
                "user_id": user_id,
                "username": username,
                "credits": initial_credits
            }
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Username already exists")

@app.get("/stats")
async def get_stats():
    """Get global statistics"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        week_start = get_week_start(conn)
        last_placement = get_last_placement_time(conn)
        current_cap = get_current_cap(conn)
        
        cursor.execute("SELECT COUNT(*) FROM pixels")
        total_pixels = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM placements
            WHERE placed_at >= ?
        """, (week_start.isoformat(),))
        week_placements = cursor.fetchone()[0]
        
        return {
            "board_size": BOARD_SIZE,
            "total_pixels_placed": total_pixels,
            "week_start": week_start.isoformat(),
            "week_placements": week_placements,
            "last_placement": last_placement.isoformat(),
            "current_cap_credits": current_cap,
            "current_cap_dollars": current_cap / 100000
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
