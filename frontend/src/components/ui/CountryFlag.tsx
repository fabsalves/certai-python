interface Props {
  dialCode: string;
  className?: string;
}

export function CountryFlag({ dialCode, className = "phone-field__flag" }: Props) {
  switch (dialCode) {
    case "55":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" rx="1" fill="#009B3A" />
          <polygon points="10,1.5 18.5,7 10,12.5 1.5,7" fill="#FFDF00" />
          <circle cx="10" cy="7" r="3.2" fill="#002776" />
          <path d="M7.2 7a2.8 2.8 0 0 1 5.6 0" fill="none" stroke="#FFF" strokeWidth="0.6" />
        </svg>
      );
    case "1":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#B22234" rx="1" />
          <path d="M0 2h20M0 4h20M0 6h20M0 8h20M0 10h20M0 12h20" stroke="#FFF" strokeWidth="1.1" />
          <rect width="8" height="7.5" fill="#3C3B6E" rx="0.5" />
        </svg>
      );
    case "351":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#FF0000" rx="1" />
          <rect width="8" height="14" fill="#006600" rx="1" />
          <circle cx="8" cy="7" r="2.4" fill="#FFCC00" stroke="#FFF" strokeWidth="0.4" />
        </svg>
      );
    case "54":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#FFF" rx="1" />
          <rect width="20" height="4.67" fill="#74ACDF" />
          <rect y="9.33" width="20" height="4.67" fill="#74ACDF" />
          <circle cx="10" cy="7" r="2.2" fill="#F6B40E" />
        </svg>
      );
    case "598":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#FFF" rx="1" />
          <rect y="4.67" width="20" height="4.67" fill="#0038A8" />
          <path
            d="M4 4.5 5.2 7.8 8.8 7.8 5.8 9.9 7 13.2 4 11.1 1 13.2 2.2 9.9-.8 7.8 2.8 7.8Z"
            fill="#FFDD00"
            transform="scale(0.55) translate(4,1)"
          />
        </svg>
      );
    case "595":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#FFF" rx="1" />
          <rect width="20" height="4.67" fill="#D52B1E" />
          <rect y="9.33" width="20" height="4.67" fill="#0038A8" />
          <circle cx="10" cy="7" r="2" fill="#FFE900" />
        </svg>
      );
    case "56":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#D52B1E" rx="1" />
          <rect width="20" height="7" fill="#FFF" />
          <rect width="7" height="14" fill="#0039A6" rx="1" />
        </svg>
      );
    case "57":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#FFCD00" rx="1" />
          <rect y="7" width="20" height="3.5" fill="#003893" />
          <rect y="10.5" width="20" height="3.5" fill="#CE1126" />
        </svg>
      );
    case "52":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#FFF" rx="1" />
          <rect width="7" height="14" fill="#006847" rx="1" />
          <rect x="13" width="7" height="14" fill="#CE1126" rx="1" />
          <circle cx="10" cy="7" r="2" fill="#BC955C" />
        </svg>
      );
    case "49":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#FFCE00" rx="1" />
          <rect width="20" height="9.33" fill="#DD0000" />
          <rect width="20" height="4.67" fill="#000" />
        </svg>
      );
    case "44":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#012169" rx="1" />
          <path d="M0 0 20 14M20 0 0 14" stroke="#FFF" strokeWidth="2.2" />
          <path d="M0 0 20 14M20 0 0 14" stroke="#C8102E" strokeWidth="1.1" />
          <path d="M10 0v14M0 7h20" stroke="#FFF" strokeWidth="3.2" />
          <path d="M10 0v14M0 7h20" stroke="#C8102E" strokeWidth="1.8" />
        </svg>
      );
    case "34":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#AA151B" rx="1" />
          <rect y="3.5" width="20" height="7" fill="#F1BF00" />
        </svg>
      );
    case "33":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#EF4135" rx="1" />
          <rect width="13.3" height="14" fill="#FFF" />
          <rect width="6.7" height="14" fill="#0055A4" rx="1" />
        </svg>
      );
    case "39":
      return (
        <svg className={className} viewBox="0 0 20 14" aria-hidden>
          <rect width="20" height="14" fill="#CE2B37" rx="1" />
          <rect width="13.3" height="14" fill="#FFF" />
          <rect width="6.7" height="14" fill="#009246" rx="1" />
        </svg>
      );
    default:
      return (
        <span className={`${className} phone-field__flag-fallback`} aria-hidden>
          +
        </span>
      );
  }
}
