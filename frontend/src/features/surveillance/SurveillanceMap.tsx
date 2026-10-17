import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Badge, dateTime, human } from '../../components/ui'
import type { DiseaseCase, Outbreak } from '../../types'

export const riskColors: Record<string, string> = { LOW: '#348660', MODERATE: '#b78a19', HIGH: '#cd742e', CRITICAL: '#c74652' }
const coordinates = (c: DiseaseCase): [number, number] => [c.location.coordinates[1], c.location.coordinates[0]]
export const isConfirmedCluster = (cluster: Outbreak) => ['confirmed_outbreak', 'confirmed'].includes(cluster.status)

function FitRecords({ cases, filterKey }: { cases: DiseaseCase[]; filterKey: string }) {
  const map = useMap()
  const lastKey = useRef<string | null>(null)
  useEffect(() => {
    if (!cases.length || lastKey.current === filterKey) return
    map.fitBounds(L.latLngBounds(cases.map(coordinates)), { padding: [45, 45], maxZoom: 13, animate: false })
    lastKey.current = filterKey
  }, [cases, filterKey, map])
  return null
}

function FocusHotspot({ selected }: { selected: Outbreak | null }) {
  const map = useMap()
  const lastId = useRef<string | null>(null)
  useEffect(() => {
    if (!selected || selected.id === lastId.current) return
    const center = L.latLng(selected.center.coordinates[1], selected.center.coordinates[0])
    map.fitBounds(center.toBounds(Math.max(1500, selected.radius_km * 2400)), { padding: [30, 30], maxZoom: 13, animate: false })
    lastId.current = selected.id
  }, [selected, map])
  return null
}

function ReportPopup({ item }: { item: DiseaseCase }) {
  return <div className="map-popup"><strong>{item.animal_name} · {item.pashu_id}</strong>
    <p>{item.triage?.suspected_disease || 'Assessment pending'}</p>
    {item.risk && <Badge value={item.risk.level}/>} <Badge value={item.confirmation_status}/>
    <p>{item.village} · {human(item.species)}<br/>{dateTime(item.reported_at)}</p>
    <Link to={`/cases/${item.id}`}>Open health report →</Link>
  </div>
}

/** Screen-space buckets group markers for readability; they never define an outbreak. */
function ReportMarkers({ cases, groupMarkers }: { cases: DiseaseCase[]; groupMarkers: boolean }) {
  const map = useMap()
  const [zoom, setZoom] = useState(map.getZoom())
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) })
  useEffect(() => setZoom(map.getZoom()), [map])
  const groups = useMemo(() => {
    const buckets = new Map<string, DiseaseCase[]>()
    for (const item of cases) {
      const point = map.project(coordinates(item), zoom)
      const key = groupMarkers ? `${Math.floor(point.x / 48)}:${Math.floor(point.y / 48)}` : item.id
      const bucket = buckets.get(key) || []
      bucket.push(item); buckets.set(key, bucket)
    }
    return Array.from(buckets.entries())
  }, [cases, groupMarkers, map, zoom])
  return <>{groups.map(([key, items]) => {
    if (items.length === 1) {
      const item = items[0]
      const confirmed = item.confirmation_status === 'confirmed'
      const color = riskColors[item.risk?.level || ''] || '#73847d'
      return <CircleMarker key={key} center={coordinates(item)} radius={confirmed ? 9 : 7}
        pathOptions={{ color: confirmed ? '#142c45' : color, weight: confirmed ? 3 : 2, fillColor: color, fillOpacity: confirmed ? 1 : 0.55, dashArray: confirmed ? undefined : '3 2' }}>
        <Tooltip>{item.animal_name} · {item.risk?.level || 'Unassessed'} · {confirmed ? 'Lab confirmed' : human(item.confirmation_status)}</Tooltip>
        <Popup><ReportPopup item={item}/></Popup>
      </CircleMarker>
    }
    const center: [number, number] = [items.reduce((n, c) => n + c.location.coordinates[1], 0) / items.length, items.reduce((n, c) => n + c.location.coordinates[0], 0) / items.length]
    const highest = items.reduce((selected, item) => (item.risk?.score || 0) > (selected.risk?.score || 0) ? item : selected)
    const confirmed = items.filter(item => item.confirmation_status === 'confirmed').length
    return <CircleMarker key={key} center={center} radius={Math.min(27, 13 + Math.log2(items.length) * 3)} pathOptions={{ color: '#fff', weight: 2, fillColor: riskColors[highest.risk?.level || ''] || '#73847d', fillOpacity: 0.93 }}>
      <Tooltip permanent direction="center" className="marker-group-number" opacity={1}>{items.length}</Tooltip>
      <Popup><div className="map-popup"><strong>{items.length} reports in this marker group</strong><p>{confirmed} lab confirmed · {items.length - confirmed} unconfirmed</p>
        <p>Visual marker grouping only. Outbreak alerts are scored separately.</p>
        <button className="button secondary compact" onClick={() => map.setView(center, Math.min(map.getMaxZoom(), map.getZoom() + 2))}>Zoom into reports</button>
        <ul>{items.slice(0, 6).map(item => <li key={item.id}><Link to={`/cases/${item.id}`}>{item.animal_name} · {item.risk?.level || 'Unassessed'}</Link></li>)}</ul>
        {items.length > 6 && <small>Zoom in or switch off marker grouping for more reports.</small>}
      </div></Popup>
    </CircleMarker>
  })}</>
}

/** Additive radial kernels produce a report-density raster from actual case coordinates. */
function DensityLayer({ cases }: { cases: DiseaseCase[] }) {
  const map = useMap()
  useEffect(() => {
    const pane = map.getPane('report-density') || map.createPane('report-density')
    pane.style.zIndex = '350'; pane.style.pointerEvents = 'none'
    const canvas = L.DomUtil.create('canvas', 'leaflet-layer leaflet-zoom-hide report-density-canvas', pane) as HTMLCanvasElement
    canvas.setAttribute('aria-hidden', 'true')
    const context = canvas.getContext('2d', { willReadFrequently: true })
    if (!context) { canvas.remove(); return }
    let disposed = false
    const draw = () => {
      if (disposed || !canvas.isConnected || !map.getContainer().isConnected) return
      const size = map.getSize()
      // Resize events can arrive while the map is hidden or unmounting.
      // getImageData rejects zero dimensions; the next visible resize redraws it.
      if (size.x < 1 || size.y < 1) return
      canvas.width = size.x; canvas.height = size.y
      L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]))
      context.clearRect(0, 0, size.x, size.y)
      context.globalCompositeOperation = 'lighter'
      for (const item of cases) {
        const point = map.latLngToContainerPoint(coordinates(item))
        const radius = 42
        if (point.x < -radius || point.y < -radius || point.x > size.x + radius || point.y > size.y + radius) continue
        const weight = 0.12 + (item.risk?.score || 0) / 100 * 0.22
        const gradient = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius)
        gradient.addColorStop(0, `rgba(255,0,0,${weight})`)
        gradient.addColorStop(1, 'rgba(255,0,0,0)')
        context.fillStyle = gradient; context.fillRect(point.x - radius, point.y - radius, radius * 2, radius * 2)
      }
      const pixels = context.getImageData(0, 0, size.x, size.y)
      for (let i = 0; i < pixels.data.length; i += 4) {
        const intensity = pixels.data[i + 3] / 255
        if (!intensity) continue
        pixels.data[i] = Math.round(35 + 205 * intensity)
        pixels.data[i + 1] = Math.round(177 - 112 * intensity)
        pixels.data[i + 2] = Math.round(148 - 98 * intensity)
        pixels.data[i + 3] = Math.min(210, Math.round(intensity * 390))
      }
      context.globalCompositeOperation = 'source-over'; context.putImageData(pixels, 0, 0)
    }
    map.on('moveend zoomend resize', draw); draw()
    return () => { disposed = true; map.off('moveend zoomend resize', draw); canvas.remove() }
  }, [cases, map])
  return null
}

export function SurveillanceMap({ cases, clusters, selected, select, filterKey, markers, density, groupMarkers }: {
  cases: DiseaseCase[]; clusters: Outbreak[]; selected: Outbreak | null; select: (id: string) => void;
  filterKey: string; markers: boolean; density: boolean; groupMarkers: boolean
}) {
  const [tileFailure, setTileFailure] = useState(false)
  return <div data-guide="outbreak-map" className="surveillance-map-wrap">
    {tileFailure && <p className="map-tile-notice" role="status">Basemap tiles could not load. Report overlays and the hotspot list remain available.</p>}
    <MapContainer className="surveillance-map" center={[18.62, 73.8]} zoom={11} maxZoom={19} scrollWheelZoom={false} aria-label="Livestock disease reports and scored outbreak clusters">
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' eventHandlers={{ tileerror: () => setTileFailure(true) }}/>
      <FitRecords cases={cases} filterKey={filterKey}/><FocusHotspot selected={selected}/>
      {density && <DensityLayer cases={cases}/>}
      {clusters.map(cluster => <Circle key={cluster.id} center={[cluster.center.coordinates[1], cluster.center.coordinates[0]]} radius={cluster.radius_km * 1000}
        pathOptions={{ color: isConfirmedCluster(cluster) ? '#183853' : riskColors[cluster.level] || '#d07b37', weight: selected?.id === cluster.id ? 3 : 2, dashArray: isConfirmedCluster(cluster) ? undefined : '7 6', fillOpacity: selected?.id === cluster.id ? 0.12 : 0.04 }} eventHandlers={{ click: () => select(cluster.id) }}>
        <Tooltip>{cluster.suspected_disease} · {cluster.case_count} reports · Cluster score {cluster.score}</Tooltip>
        <Popup><div className="map-popup"><strong>{cluster.suspected_disease}</strong><p>{human(cluster.status)} · {cluster.case_count} reports<br/>Cluster score {cluster.score} / 100</p><button className="button secondary compact" onClick={() => select(cluster.id)}>Inspect hotspot details</button></div></Popup>
      </Circle>)}
      {markers && <ReportMarkers cases={cases} groupMarkers={groupMarkers}/>}
    </MapContainer>
  </div>
}
