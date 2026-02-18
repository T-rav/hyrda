import React, { useState } from 'react'
import { useHydraSocket } from './hooks/useHydraSocket'
import { useHumanInput } from './hooks/useHumanInput'
import { Header } from './components/Header'
import { WorkerList } from './components/WorkerList'
import { TranscriptView } from './components/TranscriptView'
import { PRTable } from './components/PRTable'
import { ReviewTable } from './components/ReviewTable'
import { EventLog } from './components/EventLog'
import { HumanInputBanner } from './components/HumanInputBanner'

const TABS = ['transcript', 'prs', 'reviews', 'timeline']

export default function App() {
  const state = useHydraSocket()
  const { requests, submit } = useHumanInput()
  const [selectedWorker, setSelectedWorker] = useState(null)
  const [activeTab, setActiveTab] = useState('transcript')

  return (
    <div style={styles.layout}>
      <Header
        batchNum={state.batchNum}
        workers={state.workers}
        prsCount={state.prs.length}
        mergedCount={state.mergedCount}
        phase={state.phase}
        connected={state.connected}
      />

      <WorkerList
        workers={state.workers}
        selectedWorker={selectedWorker}
        onSelect={setSelectedWorker}
      />

      <div style={styles.main}>
        <HumanInputBanner requests={requests} onSubmit={submit} />

        <div style={styles.tabs}>
          {TABS.map((tab) => (
            <div
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                ...styles.tab,
                ...(activeTab === tab ? styles.tabActive : {}),
              }}
            >
              {tab === 'prs' ? 'Pull Requests' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </div>
          ))}
        </div>

        <div style={styles.tabContent}>
          {activeTab === 'transcript' && (
            <TranscriptView workers={state.workers} selectedWorker={selectedWorker} />
          )}
          {activeTab === 'prs' && <PRTable prs={state.prs} />}
          {activeTab === 'reviews' && <ReviewTable reviews={state.reviews} />}
          {activeTab === 'timeline' && (
            <div style={styles.timeline}>
              {state.events.map((e, i) => (
                <div key={i} style={styles.timelineItem}>
                  <span style={styles.timelineTime}>
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </span>
                  <span style={styles.timelineType}>{e.type.replace(/_/g, ' ')}</span>
                  <span>{JSON.stringify(e.data).slice(0, 120)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <EventLog events={state.events} />
    </div>
  )
}

const styles = {
  layout: {
    display: 'grid',
    gridTemplateRows: 'auto 1fr',
    gridTemplateColumns: '280px 1fr 320px',
    height: '100vh',
  },
  main: {
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  tabs: {
    display: 'flex',
    borderBottom: '1px solid #30363d',
    background: '#161b22',
  },
  tab: {
    padding: '10px 20px',
    fontSize: 12,
    fontWeight: 600,
    color: '#8b949e',
    cursor: 'pointer',
    borderBottom: '2px solid transparent',
    transition: 'all 0.15s',
  },
  tabActive: {
    color: '#58a6ff',
    borderBottomColor: '#58a6ff',
  },
  tabContent: {
    flex: 1,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  timeline: {
    flex: 1,
    overflowY: 'auto',
    padding: 8,
  },
  timelineItem: {
    padding: '6px 8px',
    borderBottom: '1px solid #30363d',
    fontSize: 11,
  },
  timelineTime: { color: '#8b949e', marginRight: 8 },
  timelineType: { fontWeight: 600, color: '#58a6ff', marginRight: 6 },
}
