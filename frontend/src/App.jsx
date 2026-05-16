import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

function App() {
  const [formData, setFormData] = useState({
    year: 2023,
    gp: 'Bahrain',
    session_type: 'R',
    driver: 'VER',
    decision_lap: 15,
    strategy: 'pit now'
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [unregisteredData, setUnregisteredData] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'year' || name === 'decision_lap' ? parseInt(value) || value : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setUnregisteredData(null);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      
      const data = await response.json();
      
      if (data.unregistered_data) {
        setUnregisteredData(data);
      } else if (data.error) {
        setError(data.error);
      } else {
        setResult(data);
      }
    } catch (err) {
      setError("Failed to connect to the simulation server. Ensure the Python backend is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-layout">
      
      {/* Left Column: Command Panel */}
      <aside className="panel control-panel">
        <div className="panel-header">
          <h1>Strategy Cmd</h1>
          <p className="subtitle">Configure parameters and inject telemetry to simulate optimal pit windows.</p>
        </div>

        <form onSubmit={handleSubmit} className="form-grid">
          <div className="input-group">
            <label>Year</label>
            <input type="number" name="year" value={formData.year} onChange={handleChange} required />
          </div>
          <div className="input-group">
            <label>Grand Prix</label>
            <input type="text" name="gp" value={formData.gp} onChange={handleChange} required />
          </div>
          <div className="input-group">
            <label>Driver</label>
            <input type="text" name="driver" value={formData.driver} onChange={handleChange} maxLength="3" required />
            <span className="help-text">Use 3-letter abbreviation (e.g., VER, HAM).</span>
          </div>
          
          <div className="input-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label>Decision Lap</label>
              {result && <span className="help-text" style={{ margin: 0, color: 'var(--accent)' }}>TOTAL LAPS: {result.max_lap}</span>}
            </div>
            <input type="number" name="decision_lap" value={formData.decision_lap} onChange={handleChange} required />
          </div>
          
          <div className="input-group">
            <label>Strategy Choice</label>
            <select name="strategy" value={formData.strategy} onChange={handleChange}>
              <option value="pit now">Pit Now (This Lap)</option>
              <option value="pit after 3 laps">Stay Out (Pit in 3 Laps)</option>
            </select>
          </div>
          
          <button type="submit" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Simulating...' : 'Execute Simulation'}
          </button>
        </form>
      </aside>

      {/* Right Column: Telemetry Output */}
      <main className="panel telemetry-panel">
        {!loading && !result && !error && !unregisteredData && (
          <div className="telemetry-empty">
            Awaiting simulation parameters...
          </div>
        )}

        {loading && (
          <div className="car-loader-container">
            <div className="track">
              <div className="car">🏎️</div>
            </div>
            <p className="loading-text">Downloading Telemetry & Simulating...</p>
          </div>
        )}

        {unregisteredData && (
          <div className="error-card anomaly-card" style={{ animation: 'slideUp 0.3s ease-out' }}>
            <div className="anomaly-icon">⚠️</div>
            <div>
              <p style={{ textTransform: 'uppercase', letterSpacing: '1px', fontSize: '0.9rem', marginBottom: '0.5rem', fontWeight: 800 }}>Unregistered Data: {unregisteredData.title}</p>
              <p style={{ fontSize: '0.95rem', lineHeight: '1.5' }}>{unregisteredData.message}</p>
            </div>
          </div>
        )}

        {error && (
          <div className="error-card" style={{ animation: 'slideUp 0.3s ease-out' }}>
            <p style={{ textTransform: 'uppercase', letterSpacing: '1px', fontSize: '0.8rem', marginBottom: '0.5rem' }}>System Error</p>
            {error}
          </div>
        )}

        {result && !error && !unregisteredData && (
          <div className="results-container" style={{ animation: 'slideUp 0.3s ease-out' }}>
            <div className="results-header">
              <div className="race-meta">
                <span>Race: <strong>{formData.gp} {formData.year}</strong></span>
                <span>Driver: <strong>{formData.driver.toUpperCase()}</strong></span>
                <span>Decision Lap: <strong>{formData.decision_lap} / {result.max_lap}</strong></span>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '1.5rem' }}>
              <h2 style={{ fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Strategy Output</h2>
              <span className="help-text" style={{ margin: 0 }}>Pit Loss Used: {result.pit_time_loss.toFixed(1)}s</span>
            </div>
            
            <div className={`result-card ${result.net_difference <= 0 ? 'verdict-good' : 'verdict-bad'}`} style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
              <div className="result-label">Verdict</div>
              <div className={`result-value ${result.net_difference <= 0 ? 'verdict-good-text' : 'verdict-bad-text'}`} style={{ fontSize: '2rem', marginTop: '0.5rem' }}>
                {result.verdict}
              </div>
            </div>

            <div className="results-grid" style={{ marginBottom: '2rem' }}>
              <div className="result-card">
                <div className="result-label">Total Time ({result.chosen_strategy})</div>
                <div className="result-value">{result.total_time_chosen.toFixed(2)}s</div>
              </div>
              <div className="result-card">
                <div className="result-label">Total Time ({result.other_label})</div>
                <div className="result-value">{result.total_time_other.toFixed(2)}s</div>
              </div>
              <div className="result-card">
                <div className="result-label">Net Difference</div>
                <div className={`result-value ${result.net_difference <= 0 ? 'verdict-good-text' : 'verdict-bad-text'}`}>
                  {result.net_difference > 0 ? '+' : ''}{result.net_difference.toFixed(2)}s
                </div>
              </div>
            </div>

            {result.winner_time && (
              <>
                <h2 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px', borderTop: '1px solid var(--panel-border)', paddingTop: '2rem' }}>Race Comparison</h2>
                <div className="results-grid" style={{ marginBottom: '2rem' }}>
                  <div className="result-card">
                    <div className="result-label">Simulated Race ({result.driver})</div>
                    <div className="result-value">{result.simulated_total_race_time.toFixed(2)}s</div>
                  </div>
                  <div className="result-card">
                    <div className="result-label">Actual Race ({result.driver})</div>
                    <div className="result-value">{result.actual_total_race_time.toFixed(2)}s</div>
                  </div>
                  <div className="result-card">
                    <div className="result-label">Actual Winner ({result.winner_name})</div>
                    <div className="result-value">{result.winner_time.toFixed(2)}s</div>
                  </div>
                  <div className={`result-card ${result.delta_to_winner <= 0 ? 'verdict-good' : 'verdict-bad'}`} style={{ gridColumn: '1 / -1', alignItems: 'center' }}>
                    <div className="result-label">Simulated Delta to Winner</div>
                    <div className={`result-value ${result.delta_to_winner <= 0 ? 'verdict-good-text' : 'verdict-bad-text'}`}>
                      {result.delta_to_winner > 0 ? '+' : ''}{result.delta_to_winner.toFixed(2)}s
                    </div>
                  </div>
                </div>

                <div className="graph-container">
                  <h2 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Pit Stop Comparison</h2>
                  <div style={{ width: '100%', height: 150, marginBottom: '2rem' }}>
                    <ResponsiveContainer>
                      <BarChart layout="vertical" data={[
                        { name: `Actual Winner (${result.winner_name})`, time: result.winner_pit_time_loss || 20 },
                        { name: `Your Driver (${result.driver})`, time: result.pit_time_loss }
                      ]} margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
                        <XAxis type="number" hide />
                        <YAxis type="category" dataKey="name" stroke="#ffffff" width={150} tick={{ fill: '#ffffff', fontSize: '0.85rem', fontWeight: 600 }} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#1e1e24', borderColor: '#2c2c35', borderRadius: '8px', color: '#ffffff' }}
                          itemStyle={{ color: '#ffffff', fontWeight: 'bold' }}
                          formatter={(value) => [`${value.toFixed(2)}s`, 'Pit Lane Time']}
                        />
                        <Bar dataKey="time" radius={[0, 4, 4, 0]} barSize={20}>
                          <Cell fill="#00e676" />
                          <Cell fill="#e10600" />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {result.graph_data && result.graph_data.length > 0 && (
                  <div className="graph-container">
                    <h2 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Pace Trace</h2>
                    <div style={{ width: '100%', height: 350 }}>
                      <ResponsiveContainer>
                        <LineChart data={result.graph_data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#2c2c35" vertical={false} />
                          <XAxis dataKey="lap" stroke="#888890" tick={{ fill: '#888890' }} />
                          <YAxis stroke="#888890" tick={{ fill: '#888890' }} domain={['dataMin', 'dataMax']} tickFormatter={(tick) => `${(tick/60).toFixed(1)}m`} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#1e1e24', borderColor: '#2c2c35', borderRadius: '8px' }}
                            itemStyle={{ fontWeight: 'bold' }}
                            formatter={(value) => [`${value.toFixed(1)}s`, '']}
                            labelFormatter={(label) => `Lap ${label}`}
                          />
                          <Legend wrapperStyle={{ paddingTop: '10px' }} />
                          <Line type="monotone" dataKey="winner_time" name={`Winner (${result.winner_name})`} stroke="#00e676" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="actual_time" name={`Actual Team (${result.driver})`} stroke="#888890" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="simulated_time" name={`Simulated Strategy (${result.driver})`} stroke="#e10600" strokeWidth={3} dot={false} activeDot={{ r: 6 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>

    </div>
  );
}

export default App;
