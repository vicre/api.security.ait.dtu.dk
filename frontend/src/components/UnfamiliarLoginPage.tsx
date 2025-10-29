import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Map, { Layer, MapRef, Popup, Source } from 'react-map-gl/maplibre';
import type { Feature, FeatureCollection, Point } from 'geojson';
import type { Map as MaplibreMap } from 'maplibre-gl';
import { LngLatBounds } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './UnfamiliarLoginPage.css';

interface UnfamiliarLoginPageProps {
  accessToken?: string | null;
  onClose: () => void;
}

type RawIdentityEvent = Record<string, unknown>;

interface SignInEvent {
  id: string;
  timestamp: string;
  displayLocation: string;
  ipAddress?: string;
  latitude?: number;
  longitude?: number;
  protocol?: string;
  status?: string;
  raw: RawIdentityEvent;
}

interface IdentityLogonResponse {
  results?: RawIdentityEvent[];
}

const LATITUDE_KEYS = [
  'LocationLatitude',
  'LocationLat',
  'Latitude',
  'LatitudeDegrees',
  'GeoLatitude',
  'Lat',
  'lat'
] as const;

const LONGITUDE_KEYS = [
  'LocationLongitude',
  'LocationLong',
  'Longitude',
  'LongitudeDegrees',
  'GeoLongitude',
  'Lon',
  'Long',
  'lon'
] as const;

const TIMESTAMP_KEYS = ['Timestamp', 'TimeGenerated', 'EventTime', 'CreatedDateTime'] as const;

const LOCATION_KEYS = [
  'Location',
  'LocationCity',
  'City',
  'LocationState',
  'State',
  'LocationCountryOrRegion',
  'CountryOrRegion',
  'Country'
] as const;

const IP_ADDRESS_KEYS = [
  'IPAddress',
  'IpAddress',
  'ClientIP',
  'ClientIpAddress',
  'SourceIp',
  'SourceIpAddress'
] as const;

const PROTOCOL_KEYS = ['Protocol', 'AuthenticationProtocol', 'ClientAppUsed'] as const;
const STATUS_KEYS = ['AuthenticationRequirement', 'ResultType', 'Status'] as const;

const DEFAULT_VIEW = {
  longitude: 12,
  latitude: 40,
  zoom: 1.2,
  pitch: 30,
  bearing: 0
};

const getFirstString = (record: RawIdentityEvent, keys: readonly string[]): string | undefined => {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim().length > 0) {
      return value.trim();
    }
  }
  return undefined;
};

const getFirstNumber = (record: RawIdentityEvent, keys: readonly string[]): number | undefined => {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string') {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return undefined;
};

const getFirstTimestamp = (record: RawIdentityEvent): string | undefined => {
  const stringTimestamp = getFirstString(record, TIMESTAMP_KEYS);
  if (stringTimestamp) {
    return stringTimestamp;
  }
  for (const key of TIMESTAMP_KEYS) {
    const value = record[key];
    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return value.toISOString();
    }
  }
  return undefined;
};

const buildDisplayLocation = (record: RawIdentityEvent): string => {
  const city = getFirstString(record, ['LocationCity', 'City']);
  const country = getFirstString(record, ['LocationCountryOrRegion', 'CountryOrRegion', 'Country']);
  const location = getFirstString(record, LOCATION_KEYS);

  if (city && country) {
    return `${city}, ${country}`;
  }
  if (location) {
    return location;
  }
  if (city) {
    return city;
  }
  if (country) {
    return country;
  }
  return 'Unknown location';
};

const formatTimestamp = (timestamp: string): string => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

const transformEvents = (rawEvents: RawIdentityEvent[]): SignInEvent[] => {
  return rawEvents
    .map((raw, index) => {
      const timestamp = getFirstTimestamp(raw);
      const latitude = getFirstNumber(raw, LATITUDE_KEYS);
      const longitude = getFirstNumber(raw, LONGITUDE_KEYS);
      const ipAddress = getFirstString(raw, IP_ADDRESS_KEYS);
      const protocol = getFirstString(raw, PROTOCOL_KEYS);
      const status = getFirstString(raw, STATUS_KEYS);
      const displayLocation = buildDisplayLocation(raw);
      const idCandidate =
        getFirstString(raw, ['EventId', 'Id', 'ActivityId', 'LogonId']) ??
        `${timestamp ?? 'event'}-${index}`;

      if (!timestamp) {
        return null;
      }

      return {
        id: idCandidate,
        timestamp,
        displayLocation,
        ipAddress: ipAddress ?? undefined,
        latitude,
        longitude,
        protocol: protocol ?? undefined,
        status: status ?? undefined,
        raw
      } satisfies SignInEvent;
    })
    .filter((event): event is SignInEvent => event !== null)
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
};

const buildGeoJson = (events: SignInEvent[]): FeatureCollection<Point> => {
  const features: Feature<Point>[] = events
    .filter(event => typeof event.latitude === 'number' && typeof event.longitude === 'number')
    .map(event => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [event.longitude as number, event.latitude as number]
      },
      properties: {
        id: event.id,
        location: event.displayLocation,
        timestamp: event.timestamp,
        ipAddress: event.ipAddress ?? ''
      }
    }));

  return {
    type: 'FeatureCollection',
    features
  };
};

const locationLayer: Layer = {
  id: 'identity-events',
  type: 'circle',
  paint: {
    'circle-radius': [
      'interpolate',
      ['linear'],
      ['zoom'],
      1,
      4,
      5,
      8
    ],
    'circle-color': '#f97316',
    'circle-stroke-color': '#111827',
    'circle-stroke-width': 1.5,
    'circle-opacity': 0.85
  }
};

const DEFAULT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

const UnfamiliarLoginPage: React.FC<UnfamiliarLoginPageProps> = ({ accessToken, onClose }) => {
  const [username, setUsername] = useState('');
  const [lookback, setLookback] = useState('7d');
  const [events, setEvents] = useState<SignInEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [activeUser, setActiveUser] = useState<string>('');
  const [activeLookback, setActiveLookback] = useState<string>('7d');

  const mapRef = useRef<MapRef | null>(null);

  const eventsWithCoordinates = useMemo(
    () => events.filter(event => typeof event.latitude === 'number' && typeof event.longitude === 'number'),
    [events]
  );

  const geoJson = useMemo(() => buildGeoJson(events), [events]);

  const selectedEvent = useMemo(
    () => events.find(event => event.id === selectedEventId) ?? null,
    [events, selectedEventId]
  );

  const fitMapToEvents = useCallback(
    (map: MaplibreMap, targetEvents: SignInEvent[]) => {
      if (!map || targetEvents.length === 0) {
        return;
      }

      const bounds = new LngLatBounds();
      targetEvents.forEach(event => {
        if (typeof event.longitude === 'number' && typeof event.latitude === 'number') {
          bounds.extend([event.longitude, event.latitude]);
        }
      });

      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, {
          padding: 60,
          duration: 1200
        });
      }
    },
    []
  );

  useEffect(() => {
    const mapInstance = mapRef.current?.getMap();
    if (mapInstance && eventsWithCoordinates.length > 0) {
      fitMapToEvents(mapInstance, eventsWithCoordinates);
    }
  }, [eventsWithCoordinates, fitMapToEvents]);

  const handleSelectEvent = (event: SignInEvent) => {
    setSelectedEventId(event.id);
    if (typeof event.longitude === 'number' && typeof event.latitude === 'number') {
      const mapInstance = mapRef.current?.getMap();
      mapInstance?.flyTo({
        center: [event.longitude, event.latitude],
        zoom: Math.max(mapInstance.getZoom(), 3.5),
        speed: 0.8,
        pitch: 45
      });
    }
  };

  const fetchIdentityEvents = async (targetUser: string, windowParam: string) => {
    if (!targetUser.trim()) {
      setError('Please enter a username to look up sign-ins.');
      return;
    }
    if (!accessToken) {
      setError('Azure AD access token missing. Please sign in again.');
      return;
    }

    setLoading(true);
    setError(null);
    setSelectedEventId(null);

    try {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
      const endpoint = `${baseUrl}/graph/v1.0/identitylogonevents/${encodeURIComponent(targetUser)}`;
      const url = windowParam ? `${endpoint}?lookback=${encodeURIComponent(windowParam)}` : endpoint;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Request failed with status ${response.status}`);
      }

      const payload = (await response.json()) as IdentityLogonResponse;
      const rawResults = Array.isArray(payload?.results) ? payload.results : [];
      const transformed = transformEvents(rawResults);

      if (transformed.length === 0) {
        setEvents([]);
        setError('No sign-in activity found for this user in the selected window.');
        setActiveUser(targetUser);
        setActiveLookback(windowParam || '7d');
        return;
      }

      const primarySelection =
        transformed.find(event => typeof event.latitude === 'number' && typeof event.longitude === 'number') ??
        transformed[0];

      setEvents(transformed);
      setSelectedEventId(primarySelection.id);
      setActiveUser(targetUser);
      setActiveLookback(windowParam || '7d');
    } catch (err) {
      console.error('Failed to load IdentityLogonEvents', err);
      const fallbackMessage =
        err instanceof Error ? err.message : 'An unexpected error occurred while loading sign-ins.';
      setError(fallbackMessage);
      setEvents([]);
      setActiveUser('');
      setActiveLookback(windowParam || '7d');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void fetchIdentityEvents(username, lookback);
  };

  return (
    <div className="unfamiliar-login-overlay" role="dialog" aria-modal="true">
      <div className="signin-activity-modal">
        <header className="signin-activity-header">
          <div>
            <h2>Identity Sign-in Activity</h2>
            <p>Investigate sign-ins per user over a configurable lookback window.</p>
          </div>
          <button className="close-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        <form className="signin-controls" onSubmit={handleSubmit}>
          <div className="input-group">
            <label htmlFor="signin-username">User Principal Name</label>
            <input
              id="signin-username"
              type="text"
              value={username}
              onChange={event => setUsername(event.target.value)}
              placeholder="e.g. vicre@dtu.dk"
              autoFocus
              required
              disabled={loading}
            />
          </div>
          <div className="input-group">
            <label htmlFor="signin-lookback">Lookback Window</label>
            <input
              id="signin-lookback"
              type="text"
              value={lookback}
              onChange={event => setLookback(event.target.value)}
              placeholder="7d"
              disabled={loading}
            />
          </div>
          <button type="submit" className="submit-button" disabled={loading || !username.trim()}>
            {loading ? 'Fetching…' : 'Load sign-ins'}
          </button>
        </form>

        <section className="signin-content">
          <div className="globe-panel">
            <Map
              ref={mapRef}
              initialViewState={DEFAULT_VIEW}
              mapStyle={DEFAULT_STYLE}
              projection="globe"
              style={{ width: '100%', height: '100%' }}
              scrollZoom
              dragPan
              attributionControl={false}
            >
              <Source id="identity-events-source" type="geojson" data={geoJson}>
                <Layer {...locationLayer} />
              </Source>

              {selectedEvent &&
                typeof selectedEvent.latitude === 'number' &&
                typeof selectedEvent.longitude === 'number' && (
                  <Popup
                    latitude={selectedEvent.latitude}
                    longitude={selectedEvent.longitude}
                    anchor="bottom"
                    closeButton={false}
                    closeOnClick={false}
                  >
                    <div className="popup-content">
                      <strong>{selectedEvent.displayLocation}</strong>
                      <p>{formatTimestamp(selectedEvent.timestamp)}</p>
                      {selectedEvent.ipAddress && <p>IP: {selectedEvent.ipAddress}</p>}
                      {selectedEvent.protocol && <p>Protocol: {selectedEvent.protocol}</p>}
                      {selectedEvent.status && <p>Status: {selectedEvent.status}</p>}
                    </div>
                  </Popup>
                )}
            </Map>
            {activeUser && events.length > 0 && (
              <div className="globe-caption">
                Highlighting sign-ins for <strong>{activeUser}</strong>
                {activeLookback ? ` • lookback ${activeLookback}` : ''}
              </div>
            )}
            {eventsWithCoordinates.length === 0 && !loading && !error && events.length > 0 && (
              <div className="no-coordinates">
                No geographic coordinates were returned for these sign-ins. Full details are available in the list.
              </div>
            )}
          </div>

          <aside className="timeline-panel">
            <div className="timeline-header">
              <h3>Sign-ins</h3>
              <span>{events.length}</span>
            </div>

            {error && <div className="error-state">{error}</div>}

            {!error && !loading && events.length === 0 && (
              <div className="empty-state">
                Enter a user principal name and select “Load sign-ins” to review their activity.
              </div>
            )}

            {loading && <div className="loading-indicator">Loading sign-ins…</div>}

            <div className="timeline-list">
              {events.map(event => (
                <button
                  key={event.id}
                  onClick={() => handleSelectEvent(event)}
                  className={`timeline-item${event.id === selectedEventId ? ' active' : ''}`}
                  type="button"
                >
                  <span className="event-location">{event.displayLocation}</span>
                  <span className="event-timestamp">{formatTimestamp(event.timestamp)}</span>
                  <span className="event-meta">
                    {event.ipAddress ? `IP ${event.ipAddress}` : 'IP unknown'}
                    {event.protocol ? ` · ${event.protocol}` : ''}
                    {event.status ? ` · ${event.status}` : ''}
                  </span>
                </button>
              ))}
            </div>
          </aside>
        </section>
      </div>
    </div>
  );
};

export default UnfamiliarLoginPage;
