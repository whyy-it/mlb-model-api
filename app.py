from flask import Flask, request, jsonify
import pickle
import numpy as np
import pandas as pd
import requests
from datetime import datetime

app = Flask(__name__)

# Load your trained model
model_data = None
try:
    with open('mlb_model.pkl', 'rb') as f:
        model_data = pickle.load(f)
    print("✓ Model loaded successfully")
    print(f"  - Features: {model_data['feature_cols']}")
    print(f"  - Accuracy: {model_data['accuracy']:.2%}")
except Exception as e:
    print(f"✗ Error loading model: {e}")

@app.route('/', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Model API is running'}), 200

@app.route('/predict', methods=['POST'])
def predict():
    """
    Predict home win probability using trained model
    """
    try:
        if model_data is None:
            return jsonify({'error': 'Model not loaded'}), 500
        
        data = request.get_json()
        
        if not data or 'games' not in data:
            return jsonify({'error': 'Invalid request format'}), 400
        
        games = data['games']
        predictions = []
        
        # Get team stats for current season
        team_stats = get_team_stats()
        
        for game in games:
            try:
                home_team = game.get('homeTeam', '')
                away_team = game.get('awayTeam', '')
                game_id = game.get('gameId')
                is_day_game = game.get('is_day_game', 0)
                
                # Create feature vector
                features = create_features(
                    home_team, away_team, is_day_game, 
                    team_stats, model_data
                )
                
                if features is None:
                    # Fallback to 50% if we can't calculate features
                    pred = {
                        'gameId': game_id,
                        'homeTeam': home_team,
                        'awayTeam': away_team,
                        'homeWinProb': 50,
                        'awayWinProb': 50,
                        'overProb': game.get('overProb', 50)
                    }
                else:
                    # Scale features
                    features_scaled = model_data['scaler'].transform([features])
                    
                    # Get probability
                    home_win_prob = model_data['model'].predict_proba(features_scaled)[0][1]
                    home_win_prob_pct = int(home_win_prob * 100)
                    
                    pred = {
                        'gameId': game_id,
                        'homeTeam': home_team,
                        'awayTeam': away_team,
                        'homeWinProb': home_win_prob_pct,
                        'awayWinProb': 100 - home_win_prob_pct,
                        'overProb': game.get('overProb', 50)
                    }
                
                predictions.append(pred)
                
            except Exception as e:
                print(f"Error predicting game {game.get('gameId')}: {e}")
                # Return 50% on error
                predictions.append({
                    'gameId': game.get('gameId'),
                    'homeTeam': game.get('homeTeam'),
                    'awayTeam': game.get('awayTeam'),
                    'homeWinProb': 50,
                    'awayWinProb': 50,
                    'overProb': game.get('overProb', 50)
                })
        
        return jsonify({'predictions': predictions}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_team_stats():
    """
    Get current season team stats from MLB Stats API
    Fetches: wins, losses, runs scored, runs allowed
    """
    try:
        team_stats = {}
        
        # First, get all teams
        teams_url = 'https://statsapi.mlb.com/api/v1/teams?sportId=1'
        teams_response = requests.get(teams_url, timeout=10)
        
        if teams_response.status_code != 200:
            print(f"⚠️ Could not fetch teams: {teams_response.status_code}")
            return get_default_team_stats()
        
        teams_data = teams_response.json()
        
        for team in teams_data.get('teams', []):
            team_id = team['id']
            team_name = team['name']
            
            try:
                # Get team stats for current season
                stats_url = f'https://statsapi.mlb.com/api/v1/teams/{team_id}?hydrate=record,stats'
                stats_response = requests.get(stats_url, timeout=5)
                
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    team_info = stats_data.get('teams', [{}])[0]
                    
                    # Get record
                    record = team_info.get('record', {})
                    wins = record.get('wins', 0)
                    losses = record.get('losses', 0)
                    games_played = wins + losses
                    
                    if games_played > 0:
                        win_pct = wins / games_played
                    else:
                        win_pct = 0.5
                    
                    # Get season stats (runs, ERA, etc.)
                    season_stats = {}
                    for stat_group in team_info.get('seasonStats', []):
                        if stat_group.get('type', {}).get('displayName') == 'season':
                            season_stats = stat_group.get('stats', {})
                            break
                    
                    # Calculate average runs scored
                    runs_scored = season_stats.get('runs', 0)
                    avg_runs = (runs_scored / games_played) if games_played > 0 else 4.0
                    
                    team_stats[team_name] = {
                        'win_pct': win_pct,
                        'wins': wins,
                        'losses': losses,
                        'avg_runs': avg_runs,
                        'runs_scored': runs_scored
                    }
            except Exception as e:
                print(f"⚠️ Error fetching stats for {team_name}: {e}")
                continue
        
        if team_stats:
            print(f"✓ Loaded stats for {len(team_stats)} teams")
            return team_stats
        else:
            print("⚠️ No team stats loaded, using defaults")
            return get_default_team_stats()
        
    except Exception as e:
        print(f"⚠️ Error fetching team stats: {e}")
        return get_default_team_stats()


def get_default_team_stats():
    """Fallback stats if API fails"""
    return {
        'win_pct': 0.5,
        'avg_runs': 4.0
    }


def create_features(home_team, away_team, is_day_game, team_stats, model_data):
    """
    Create feature vector for model prediction
    Uses team stats to calculate the 11 required features
    """
    try:
        # Get team IDs (simple hash)
        home_team_id = hash(home_team) % 1000
        away_team_id = hash(away_team) % 1000
        
        # Get home team stats
        home_stats = team_stats.get(home_team, {})
        home_win_pct = home_stats.get('win_pct', 0.5)
        home_avg_runs = home_stats.get('avg_runs', 4.0)
        home_recent_form = home_win_pct  # Use current win % as proxy for recent form
        
        # Get away team stats
        away_stats = team_stats.get(away_team, {})
        away_win_pct = away_stats.get('win_pct', 0.5)
        away_avg_runs = away_stats.get('avg_runs', 4.0)
        away_recent_form = away_win_pct  # Use current win % as proxy for recent form
        
        # Normalize values to 0-1
        home_win_pct = max(0, min(1, home_win_pct))
        away_win_pct = max(0, min(1, away_win_pct))
        home_avg_runs = home_avg_runs / 10.0  # Normalize (assume max ~10 runs/game)
        away_avg_runs = away_avg_runs / 10.0
        home_recent_form = max(0, min(1, home_recent_form))
        away_recent_form = max(0, min(1, away_recent_form))
        
        # Create feature vector in order expected by model
        features = [
            home_team_id / 1000.0,  # home_team_id (normalized)
            away_team_id / 1000.0,  # away_team_id (normalized)
            is_day_game,             # is_day_game
            0.5,                     # game_length_norm (default)
            home_win_pct,            # home_win_pct
            away_win_pct,            # away_win_pct
            1.0,                     # home_field_advantage
            home_avg_runs,           # home_avg_runs (normalized)
            away_avg_runs,           # away_avg_runs (normalized)
            home_recent_form,        # home_recent_form
            away_recent_form,        # away_recent_form
        ]
        
        return features
        
    except Exception as e:
        print(f"Error creating features: {e}")
        return None


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
