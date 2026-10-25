import React from 'react';

export const PageSkeleton: React.FC<{ tiles?: boolean }> = ({ tiles = true }) => (
  <div aria-busy="true" aria-label="Загрузка">
    <div className="skeleton skeleton-title" />
    <div className="skeleton skeleton-line" />
    {tiles && (
      <div className="tiles">
        {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton skeleton-tile" />)}
      </div>
    )}
    <div className="skeleton skeleton-card" />
  </div>
);
