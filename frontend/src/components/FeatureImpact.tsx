import React from 'react';
import type { FeatureImpact } from '../api/types';
import { eur, pct } from '../format';

export const FeatureImpactTable: React.FC<{ features: FeatureImpact[]; total: number; customers: number }> = ({ features, total, customers }) => (
  <div className="table-responsive">
    <table className="clients-table impact-table">
      <thead>
        <tr>
          <th>Признак</th>
          <th className="num">Вес</th>
          <th className="num">Клиентов</th>
          <th className="num">Услуг</th>
          <th>Доля потерь</th>
          <th className="num">Потери</th>
        </tr>
      </thead>
      <tbody>
        {features.map((f) => {
          const share = total > 0 ? f.expectedLoss / total : 0;
          return (
            <tr key={f.feature} className={f.weight === 0 ? 'muted' : ''}>
              <td>
                {f.title}
                {f.kind === 'protective' && <span className="tag-protective">защитный</span>}
                {f.weight === 0 && <span className="muted"> · выключен</span>}
              </td>
              <td className="num">{f.weight.toFixed(2)}</td>
              <td className="num">{f.customers} <span className="muted">из {customers}</span></td>
              <td className="num">{f.services}</td>
              <td className="impact-cell">
                {f.kind === 'protective' ? (
                  <span className="muted">снижает риск, потерь не создаёт</span>
                ) : (
                  <>
                    <div className="impact-bar"><div style={{ width: pct(share) }} /></div>
                    <span className="muted">{pct(share)}</span>
                  </>
                )}
              </td>
              <td className="num">{f.kind === 'protective' ? '—' : eur(f.expectedLoss)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);
