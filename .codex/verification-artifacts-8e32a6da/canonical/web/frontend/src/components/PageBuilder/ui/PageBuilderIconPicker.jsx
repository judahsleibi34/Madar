/* eslint-disable react-refresh/only-export-components -- shared icon registry is intentionally colocated with its renderer */
import { createElement, useState } from "react";
import {
  ArrowRight,
  Baby,
  Bell,
  Bird,
  Bookmark,
  BookHeart,
  BookOpen,
  BriefcaseBusiness,
  CakeSlice,
  CalendarDays,
  Camera,
  Check,
  CircleOff,
  Clock,
  Church,
  Cross,
  Crown,
  Flower2,
  Flame,
  Gem,
  Gift,
  Globe2,
  Grape,
  HandHeart,
  Heart,
  HeartHandshake,
  House,
  HouseHeart,
  Leaf,
  Mail,
  MapPin,
  Moon,
  Music,
  Palette,
  PartyPopper,
  PersonStanding,
  Phone,
  ShoppingBag,
  FishSymbol,
  Sparkles,
  Star,
  Sun,
  Trophy,
  UserRound,
  UsersRound,
  Utensils,
  Wheat,
  Droplets,
  ChevronDown,
  ChevronUp,
  Zap,
} from "lucide-react";

function WeddingRings({ size = 24, strokeWidth = 1.8, ...props }) {
  return (
    <svg
      {...props}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="8" cy="14.5" r="4.75" />
      <circle cx="16" cy="14.5" r="4.75" />
      <path d="m13 7.5 3-3 3 3-3 2.25z" />
      <path d="M14.25 5.75h3.5" />
    </svg>
  );
}

export const builderIconOptions = [
  ["WeddingRings", "Wedding rings", WeddingRings, "Wedding & celebration", "ring rings marriage engagement"],
  ["Heart", "Heart", Heart, "Wedding & celebration", "love romance"],
  ["Flower2", "Flower", Flower2, "Wedding & celebration", "floral bouquet"],
  ["Gem", "Diamond", Gem, "Wedding & celebration", "gem jewelry engagement"],
  ["CakeSlice", "Wedding cake", CakeSlice, "Wedding & celebration", "cake dessert"],
  ["Gift", "Gift", Gift, "Wedding & celebration", "present"],
  ["PartyPopper", "Celebration", PartyPopper, "Wedding & celebration", "party confetti"],
  ["Sparkles", "Sparkles", Sparkles, "Wedding & celebration", "magic shine"],
  ["UsersRound", "Family", UsersRound, "Family & people", "family parents children group people"],
  ["Baby", "Baby", Baby, "Family & people", "baby child newborn infant baptism christening"],
  ["HouseHeart", "Family home", HouseHeart, "Family & people", "family house home love"],
  ["HeartHandshake", "Family care", HeartHandshake, "Family & people", "family care support together parents"],
  ["PersonStanding", "Child or person", PersonStanding, "Family & people", "child kid person portrait"],
  ["Cross", "Christian cross", Cross, "Christian & faith", "christ religion jesus"],
  ["Church", "Church", Church, "Christian & faith", "chapel religion"],
  ["BookOpen", "Open Bible", BookOpen, "Christian & faith", "scripture book"],
  ["BookHeart", "Faith book", BookHeart, "Christian & faith", "bible love"],
  ["Bird", "Dove", Bird, "Christian & faith", "peace holy spirit"],
  ["Flame", "Holy Spirit flame", Flame, "Christian & faith", "fire pentecost"],
  ["FishSymbol", "Christian fish", FishSymbol, "Christian & faith", "ichthys jesus"],
  ["Wheat", "Wheat", Wheat, "Christian & faith", "communion harvest"],
  ["Grape", "Grapes", Grape, "Christian & faith", "communion wine"],
  ["Droplets", "Baptism water", Droplets, "Christian & faith", "christening water"],
  ["HandHeart", "Faith and care", HandHeart, "Christian & faith", "charity care"],
  ["Camera", "Camera", Camera, "Events & creative", "photo photography"],
  ["CalendarDays", "Calendar", CalendarDays, "Events & creative", "date schedule"],
  ["Music", "Music", Music, "Events & creative", "song audio"],
  ["Palette", "Creative", Palette, "Events & creative", "art color"],
  ["Crown", "Crown", Crown, "Events & creative", "royal premium"],
  ["Star", "Star", Star, "Events & creative", "favorite featured"],
  ["Trophy", "Award", Trophy, "Events & creative", "winner prize"],
  ["Sun", "Sun", Sun, "Nature & places", "day light"],
  ["Moon", "Moon", Moon, "Nature & places", "night"],
  ["Leaf", "Nature", Leaf, "Nature & places", "plant eco"],
  ["MapPin", "Location", MapPin, "Nature & places", "place address"],
  ["House", "Home", House, "Nature & places", "building"],
  ["Globe2", "Website", Globe2, "Nature & places", "world internet"],
  ["ArrowRight", "Arrow", ArrowRight, "Actions & business", "next explore link"],
  ["Check", "Check", Check, "Actions & business", "done success"],
  ["Mail", "Email", Mail, "Actions & business", "message envelope"],
  ["Phone", "Phone", Phone, "Actions & business", "call contact"],
  ["BriefcaseBusiness", "Business", BriefcaseBusiness, "Actions & business", "work job"],
  ["UserRound", "Person", UserRound, "Actions & business", "user profile"],
  ["ShoppingBag", "Shop", ShoppingBag, "Actions & business", "store purchase"],
  ["Utensils", "Dining", Utensils, "Actions & business", "food restaurant"],
  ["Bell", "Notification", Bell, "Actions & business", "alert"],
  ["Bookmark", "Bookmark", Bookmark, "Actions & business", "save"],
  ["Zap", "Energy", Zap, "Actions & business", "lightning fast"],
  ["Clock", "Time", Clock, "Actions & business", "hour schedule"],
];

const builderIconCategories = [
  "Wedding & celebration",
  "Family & people",
  "Christian & faith",
  "Events & creative",
  "Nature & places",
  "Actions & business",
];

const builderIconsByName = new Map(
  builderIconOptions.map(([name, , Icon]) => [name, Icon])
);

export function BuilderIcon({ name = "Sparkles", size = 20, ...props }) {
  if (!name || name === "none") return null;
  const Icon = builderIconsByName.get(name) || Sparkles;
  const resolvedName = builderIconsByName.has(name) ? name : "Sparkles";
  return createElement(Icon, { "data-builder-icon": resolvedName, size, strokeWidth: 1.8, ...props });
}

export default function PageBuilderIconPicker({ value = "Sparkles", onChange }) {
  const collapsedIconCount = 12;
  const selectedIconIndex = builderIconOptions.findIndex(([name]) => name === value);
  const [expanded, setExpanded] = useState(selectedIconIndex >= collapsedIconCount);
  const showAll = expanded;
  const visibleOptions = showAll ? builderIconOptions : builderIconOptions.slice(0, collapsedIconCount);

  const renderOption = ([name, label, Icon]) => (
    <button
      type="button"
      className={`builder-icon-option ${value === name ? "is-selected" : ""}`}
      aria-label={label}
      aria-pressed={value === name}
      title={label}
      onClick={() => onChange?.(name)}
      key={name}
    >
      <Icon size={18} strokeWidth={1.8} />
    </button>
  );

  return (
    <div className="builder-icon-picker" role="group" aria-label="Choose an icon">
      <span className="builder-icon-picker-label">Icon <small>{builderIconOptions.length} available</small></span>
      {!showAll ? <span className="builder-icon-category-label">Popular</span> : null}
      {!showAll ? <div className="builder-icon-picker-grid">
        <button
          type="button"
          className={`builder-icon-option ${value === "none" ? "is-selected" : ""}`}
          aria-label="No icon"
          aria-pressed={value === "none"}
          title="No icon"
          onClick={() => onChange?.("none")}
        >
          <CircleOff size={18} />
        </button>
        {visibleOptions.map(renderOption)}
      </div> : (
        <div className="builder-icon-picker-results">
          {builderIconCategories.map((category) => {
            const categoryOptions = visibleOptions.filter(([, , , optionCategory]) => optionCategory === category);
            if (!categoryOptions.length) return null;
            return (
              <section className="builder-icon-category" aria-label={category} key={category}>
                <span className="builder-icon-category-label">{category}</span>
                <div className="builder-icon-picker-grid">{categoryOptions.map(renderOption)}</div>
              </section>
            );
          })}
        </div>
      )}
      <button
        type="button"
        className="builder-icon-picker-toggle"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
      >
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        {expanded ? "Collapse icons" : `Show all ${builderIconOptions.length} icons`}
      </button>
    </div>
  );
}
