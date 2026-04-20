import type { BBox } from './types'

export interface PortPreset {
  label: string
  name: string
  bbox: BBox
  date: string
}

export const PORT_PRESETS: PortPreset[] = [
  {
    label: 'Mumbai',
    name: 'mumbai',
    bbox: [72.8, 18.87, 72.97, 18.98],
    date: '2024-02-15',
  },
  {
    label: 'Chennai',
    name: 'chennai',
    bbox: [80.24, 13.04, 80.34, 13.14],
    date: '2024-02-18',
  },
  {
    label: 'Kochi',
    name: 'kochi',
    bbox: [76.22, 9.94, 76.32, 10.04],
    date: '2024-02-20',
  },
  {
    label: 'Visakhapatnam',
    name: 'visakhapatnam',
    bbox: [83.25, 17.65, 83.35, 17.75],
    date: '2024-02-22',
  },
]
