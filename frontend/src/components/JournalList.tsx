import React from 'react';
import type { Transition } from '../api/types';
import { date, transitionText } from '../format';

interface JournalListProps {
  events: Transition[];
  empty: string;
  onOpenCustomer?: (id: number) => void;
}

export const JournalList: React.FC<JournalListProps> = ({ events, empty, onOpenCustomer }) => {
  if (events.length === 0) return <p className="muted">{empty}</p>;
  return (
    <ul className="journal">
      {events.map((e, i) => (
        <li key={`${e.at}-${e.serviceId}-${e.field}-${i}`}>
          <span className="muted nowrap">{date(e.at)}</span>
          <span>
            <b>{e.serviceName}</b>
            {onOpenCustomer && (
              <> · <button className="link-btn inline" onClick={() => onOpenCustomer(e.ownerId)}>клиент {e.ownerId}</button></>
            )}
          </span>
          <span>{transitionText(e)}</span>
        </li>
      ))}
    </ul>
  );
};
