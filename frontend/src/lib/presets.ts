import type { ScenarioPreset, HourlyProfile } from '../types/energy';

/** Helper to generate a 24-hour profile from a compact descriptor */
function h(hour: number, demand: number, solar: number, tariff: number): HourlyProfile {
  return { hour, demand_kwh: demand, solar_kwh: solar, tariff_bdt_per_kwh: tariff };
}

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  // ──────────────────────────── 1. Standard Day ────────────────────────────
  {
    id: 'GRID-101',
    name: 'Standard Day — Solar Cleaning + Battery Hold',
    data: {
      scenario_id: 'GRID-101',
      operator_notes: [
        'Solar output will drop to about 20% from 1 PM to 3 PM due to panel cleaning.',
        'Do not charge the battery between 2 PM and 4 PM.',
      ],
      hours: [
        h(0, 60, 0, 5), h(1, 55, 0, 5), h(2, 50, 0, 5), h(3, 50, 0, 5),
        h(4, 55, 0, 5), h(5, 70, 5, 6), h(6, 90, 20, 7), h(7, 120, 45, 8),
        h(8, 150, 80, 9), h(9, 170, 110, 9), h(10, 180, 130, 10), h(11, 190, 140, 10),
        h(12, 200, 145, 11), h(13, 195, 30, 11), h(14, 185, 28, 12), h(15, 175, 100, 10),
        h(16, 160, 70, 9), h(17, 140, 35, 8), h(18, 130, 10, 7), h(19, 120, 0, 7),
        h(20, 100, 0, 6), h(21, 85, 0, 6), h(22, 70, 0, 5), h(23, 65, 0, 5),
      ],
      battery: {
        capacity_kwh: 200,
        initial_energy_kwh: 100,
        minimum_energy_kwh: 40,
        max_charge_kwh_per_hour: 50,
        max_discharge_kwh_per_hour: 50,
      },
    },
  },

  // ──────────────────────────── 2. Cloudy Morning ────────────────────────────
  {
    id: 'GRID-102',
    name: 'Cloudy Morning — Reduced Solar AM + High Demand',
    data: {
      scenario_id: 'GRID-102',
      operator_notes: [
        'Morning cloud cover expected. Solar reduced to 30% of normal until noon.',
        'Demand will spike due to HVAC surge at 9 AM.',
      ],
      hours: [
        h(0, 65, 0, 5), h(1, 60, 0, 5), h(2, 55, 0, 5), h(3, 55, 0, 5),
        h(4, 60, 0, 5), h(5, 75, 2, 6), h(6, 95, 6, 7), h(7, 130, 14, 8),
        h(8, 160, 24, 9), h(9, 210, 33, 10), h(10, 200, 39, 10), h(11, 195, 42, 10),
        h(12, 190, 140, 11), h(13, 185, 135, 11), h(14, 180, 130, 11), h(15, 170, 110, 10),
        h(16, 155, 75, 9), h(17, 135, 40, 8), h(18, 120, 10, 7), h(19, 110, 0, 7),
        h(20, 95, 0, 6), h(21, 80, 0, 6), h(22, 70, 0, 5), h(23, 60, 0, 5),
      ],
      battery: {
        capacity_kwh: 250,
        initial_energy_kwh: 120,
        minimum_energy_kwh: 50,
        max_charge_kwh_per_hour: 50,
        max_discharge_kwh_per_hour: 50,
      },
    },
  },

  // ──────────────────────────── 3. Event Day ────────────────────────────
  {
    id: 'GRID-103',
    name: 'Event Day — Auditorium Surge + No Discharge',
    data: {
      scenario_id: 'GRID-103',
      operator_notes: [
        'Large auditorium event from 10 AM to 2 PM. Expect 50 kWh additional demand per hour.',
        'Do not discharge battery during event hours to preserve emergency reserve.',
      ],
      hours: [
        h(0, 70, 0, 5), h(1, 65, 0, 5), h(2, 55, 0, 5), h(3, 55, 0, 5),
        h(4, 60, 0, 5), h(5, 75, 5, 6), h(6, 95, 25, 7), h(7, 125, 50, 8),
        h(8, 155, 85, 9), h(9, 175, 115, 9), h(10, 230, 135, 10), h(11, 240, 145, 10),
        h(12, 245, 140, 11), h(13, 235, 130, 11), h(14, 190, 120, 10), h(15, 170, 100, 9),
        h(16, 155, 70, 8), h(17, 140, 35, 8), h(18, 125, 10, 7), h(19, 115, 0, 7),
        h(20, 100, 0, 6), h(21, 85, 0, 6), h(22, 75, 0, 5), h(23, 65, 0, 5),
      ],
      battery: {
        capacity_kwh: 200,
        initial_energy_kwh: 150,
        minimum_energy_kwh: 60,
        max_charge_kwh_per_hour: 40,
        max_discharge_kwh_per_hour: 40,
      },
    },
  },

  // ──────────────────────────── 4. Weekend Minimal ────────────────────────────
  {
    id: 'GRID-104',
    name: 'Weekend Minimal — Low Demand + Max Solar',
    data: {
      scenario_id: 'GRID-104',
      operator_notes: [
        'Weekend schedule: campus mostly empty. Prioritize battery charging from solar.',
        'The cafeteria kitchen uses about 15 kWh extra between noon and 1 PM.',
      ],
      hours: [
        h(0, 35, 0, 4), h(1, 30, 0, 4), h(2, 28, 0, 4), h(3, 28, 0, 4),
        h(4, 30, 0, 4), h(5, 35, 5, 5), h(6, 45, 25, 5), h(7, 55, 55, 6),
        h(8, 65, 90, 6), h(9, 70, 120, 7), h(10, 75, 140, 7), h(11, 80, 150, 7),
        h(12, 95, 148, 8), h(13, 80, 140, 7), h(14, 75, 125, 7), h(15, 70, 100, 6),
        h(16, 60, 70, 6), h(17, 50, 35, 5), h(18, 45, 10, 5), h(19, 40, 0, 5),
        h(20, 38, 0, 4), h(21, 35, 0, 4), h(22, 32, 0, 4), h(23, 30, 0, 4),
      ],
      battery: {
        capacity_kwh: 200,
        initial_energy_kwh: 60,
        minimum_energy_kwh: 30,
        max_charge_kwh_per_hour: 50,
        max_discharge_kwh_per_hour: 50,
      },
    },
  },

  // ──────────────────────────── 5. Exam Week ────────────────────────────
  {
    id: 'GRID-105',
    name: 'Exam Week — Evening Study Halls + Battery Reserve',
    data: {
      scenario_id: 'GRID-105',
      operator_notes: [
        'Library and study halls open until midnight. Expect sustained demand in evening hours.',
        'Maintain at least 80 kWh battery reserve after 6 PM for emergency lighting.',
      ],
      hours: [
        h(0, 80, 0, 5), h(1, 70, 0, 5), h(2, 60, 0, 5), h(3, 55, 0, 5),
        h(4, 55, 0, 5), h(5, 70, 5, 6), h(6, 100, 20, 7), h(7, 140, 50, 8),
        h(8, 170, 85, 9), h(9, 185, 115, 10), h(10, 190, 130, 10), h(11, 195, 140, 10),
        h(12, 200, 145, 11), h(13, 195, 135, 11), h(14, 185, 125, 10), h(15, 175, 100, 9),
        h(16, 165, 70, 8), h(17, 155, 35, 8), h(18, 160, 10, 7), h(19, 165, 0, 7),
        h(20, 160, 0, 7), h(21, 150, 0, 6), h(22, 130, 0, 6), h(23, 100, 0, 5),
      ],
      battery: {
        capacity_kwh: 250,
        initial_energy_kwh: 130,
        minimum_energy_kwh: 40,
        max_charge_kwh_per_hour: 50,
        max_discharge_kwh_per_hour: 50,
      },
    },
  },

  // ──────────────────────────── 6. Summer Peak ────────────────────────────
  {
    id: 'GRID-106',
    name: 'Summer Peak — AC Load + Tariff Spike',
    data: {
      scenario_id: 'GRID-106',
      operator_notes: [
        'Heat advisory: AC load will increase by ~40% during 11 AM to 4 PM.',
        'Grid tariff spikes to 15 BDT/kWh between 1 PM and 3 PM. Minimize grid import then.',
      ],
      hours: [
        h(0, 75, 0, 5), h(1, 70, 0, 5), h(2, 65, 0, 5), h(3, 60, 0, 5),
        h(4, 65, 0, 5), h(5, 80, 8, 6), h(6, 100, 30, 7), h(7, 130, 55, 8),
        h(8, 160, 90, 9), h(9, 180, 120, 10), h(10, 200, 140, 10), h(11, 240, 148, 11),
        h(12, 260, 150, 12), h(13, 270, 145, 15), h(14, 265, 138, 15), h(15, 250, 110, 12),
        h(16, 220, 75, 10), h(17, 180, 40, 8), h(18, 150, 10, 7), h(19, 130, 0, 7),
        h(20, 110, 0, 6), h(21, 95, 0, 6), h(22, 80, 0, 5), h(23, 70, 0, 5),
      ],
      battery: {
        capacity_kwh: 300,
        initial_energy_kwh: 150,
        minimum_energy_kwh: 50,
        max_charge_kwh_per_hour: 60,
        max_discharge_kwh_per_hour: 60,
      },
    },
  },

  // ──────────────────────────── 7. Maintenance Window ────────────────────────────
  {
    id: 'GRID-107',
    name: 'Maintenance Window — Grid Outage + Battery Priority',
    data: {
      scenario_id: 'GRID-107',
      operator_notes: [
        'Scheduled grid maintenance from 2 AM to 5 AM. No grid import available during this window.',
        'Battery must handle all load during maintenance. Ensure full charge before 2 AM.',
      ],
      hours: [
        h(0, 55, 0, 5), h(1, 50, 0, 5), h(2, 50, 0, 0), h(3, 48, 0, 0),
        h(4, 48, 0, 0), h(5, 55, 3, 6), h(6, 80, 20, 7), h(7, 115, 45, 8),
        h(8, 145, 80, 9), h(9, 165, 110, 9), h(10, 175, 130, 10), h(11, 185, 140, 10),
        h(12, 190, 145, 11), h(13, 185, 135, 11), h(14, 175, 120, 10), h(15, 165, 95, 9),
        h(16, 150, 65, 8), h(17, 130, 30, 7), h(18, 115, 8, 7), h(19, 100, 0, 6),
        h(20, 85, 0, 6), h(21, 75, 0, 5), h(22, 65, 0, 5), h(23, 58, 0, 5),
      ],
      battery: {
        capacity_kwh: 200,
        initial_energy_kwh: 180,
        minimum_energy_kwh: 30,
        max_charge_kwh_per_hour: 50,
        max_discharge_kwh_per_hour: 50,
      },
    },
  },

  // ──────────────────────────── 8. Rain Day ────────────────────────────
  {
    id: 'GRID-108',
    name: 'Rain Day — No Solar All Day + Cost Optimization',
    data: {
      scenario_id: 'GRID-108',
      operator_notes: [
        'Heavy rain forecasted all day. Solar output will be near zero.',
        'Optimize for minimum grid cost. Use off-peak hours to charge battery.',
      ],
      hours: [
        h(0, 60, 0, 4), h(1, 55, 0, 4), h(2, 50, 0, 4), h(3, 50, 0, 4),
        h(4, 55, 0, 4), h(5, 65, 0, 5), h(6, 85, 2, 6), h(7, 115, 5, 7),
        h(8, 145, 8, 8), h(9, 165, 10, 9), h(10, 175, 12, 9), h(11, 180, 10, 10),
        h(12, 185, 8, 10), h(13, 180, 7, 10), h(14, 175, 5, 9), h(15, 165, 3, 9),
        h(16, 150, 2, 8), h(17, 135, 0, 7), h(18, 120, 0, 7), h(19, 110, 0, 6),
        h(20, 95, 0, 6), h(21, 80, 0, 5), h(22, 70, 0, 5), h(23, 60, 0, 4),
      ],
      battery: {
        capacity_kwh: 200,
        initial_energy_kwh: 100,
        minimum_energy_kwh: 40,
        max_charge_kwh_per_hour: 50,
        max_discharge_kwh_per_hour: 50,
      },
    },
  },

  // ──────────────────────────── 9. Graduation Ceremony ────────────────────────────
  {
    id: 'GRID-109',
    name: 'Graduation Ceremony — Afternoon Peak + Emergency Reserve',
    data: {
      scenario_id: 'GRID-109',
      operator_notes: [
        'Graduation ceremony 2 PM–5 PM. Sound systems and lighting add ~60 kWh/hour.',
        'Keep minimum 100 kWh battery reserve at all times for emergency PA system.',
      ],
      hours: [
        h(0, 55, 0, 5), h(1, 50, 0, 5), h(2, 48, 0, 5), h(3, 45, 0, 5),
        h(4, 50, 0, 5), h(5, 65, 5, 6), h(6, 85, 22, 7), h(7, 110, 48, 8),
        h(8, 140, 82, 9), h(9, 160, 112, 9), h(10, 170, 132, 10), h(11, 180, 142, 10),
        h(12, 185, 145, 11), h(13, 180, 138, 11), h(14, 240, 128, 12), h(15, 245, 105, 12),
        h(16, 235, 72, 11), h(17, 160, 38, 8), h(18, 130, 10, 7), h(19, 115, 0, 7),
        h(20, 95, 0, 6), h(21, 80, 0, 6), h(22, 70, 0, 5), h(23, 60, 0, 5),
      ],
      battery: {
        capacity_kwh: 250,
        initial_energy_kwh: 140,
        minimum_energy_kwh: 100,
        max_charge_kwh_per_hour: 50,
        max_discharge_kwh_per_hour: 50,
      },
    },
  },

  // ──────────────────────────── 10. Normal Operations (Distractor Test) ────────────────────────────
  {
    id: 'GRID-110',
    name: 'Normal Operations — Distractor Note Test',
    data: {
      scenario_id: 'GRID-110',
      operator_notes: [
        'The campus gardener mentioned flowers are blooming nicely this week.',
        'Parking lot B will be repainted next Tuesday.',
        'Cafeteria menu changed to include more vegetarian options.',
      ],
      hours: [
        h(0, 60, 0, 5), h(1, 55, 0, 5), h(2, 52, 0, 5), h(3, 50, 0, 5),
        h(4, 52, 0, 5), h(5, 68, 5, 6), h(6, 88, 22, 7), h(7, 118, 48, 8),
        h(8, 148, 82, 9), h(9, 168, 112, 9), h(10, 178, 132, 10), h(11, 185, 142, 10),
        h(12, 192, 145, 11), h(13, 188, 140, 11), h(14, 180, 128, 10), h(15, 170, 105, 9),
        h(16, 155, 72, 8), h(17, 138, 38, 7), h(18, 122, 10, 7), h(19, 110, 0, 6),
        h(20, 95, 0, 6), h(21, 82, 0, 5), h(22, 70, 0, 5), h(23, 62, 0, 5),
      ],
      battery: {
        capacity_kwh: 200,
        initial_energy_kwh: 100,
        minimum_energy_kwh: 40,
        max_charge_kwh_per_hour: 50,
        max_discharge_kwh_per_hour: 50,
      },
    },
  },
];

export function getPresetById(id: string): ScenarioPreset | undefined {
  return SCENARIO_PRESETS.find((p) => p.id === id);
}
