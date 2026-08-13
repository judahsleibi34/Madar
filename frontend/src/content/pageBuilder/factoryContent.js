export const factoryContent = {
  en: {
    fields: {
      untitled: "Untitled field",
      options: ["Option 1", "Option 2"],
      scaleMin: "Low",
      scaleMax: "High",
    },
    collection: {
      name: "Requests",
      description: "Front-end collection model. Connect this to your backend later.",
      defaultFields: {
        title: "Title",
        status: "Status",
        statusOptions: ["New", "Pending", "Approved", "Rejected"],
        createdBy: "Created by",
      },
    },
    form: {
      sectionTitle: "Page 1",
      title: "Untitled Form",
      description: "Use this form to collect information.",
      successMessage: "Thank you. Your response has been submitted.",
      defaultFields: {
        fullName: "Full name",
        email: "Email",
        details: "Details",
      },
    },
    elements: {
      heading: {
        name: "Heading",
        content: "Build your business app without code",
      },
      text: {
        name: "Text",
        content:
          "Design pages, collect responses, manage roles, prototype workflows, and prepare everything for backend integration later.",
      },
      button: {
        name: "Button",
        content: "Get started",
      },
      imageButton: {
        name: "Image Button",
      },
      image: {
        name: "Image",
      },
      video: {
        name: "Video",
      },
      document: {
        name: "File Viewer",
        title: "View document",
        description: "Open this file in a focused viewer.",
      },
      photoProofing: {
        name: "Photo Proofing",
        content:
          "Portrait by the window\nNatural light portrait\nhttps://images.unsplash.com/photo-1519741497674-611481863552?w=1400&q=88&auto=format&fit=crop\n\nGolden hour walk\nOutdoor couple session\nhttps://images.unsplash.com/photo-1606800052052-a08af7148866?w=1400&q=88&auto=format&fit=crop\n\nQuiet moment\nEditorial wedding detail\nhttps://images.unsplash.com/photo-1523438885200-e635ba2c371e?w=1400&q=88&auto=format&fit=crop\n\nCelebration\nA candid favorite from the session\nhttps://images.unsplash.com/photo-1537633552985-df8429e8048b?w=1400&q=88&auto=format&fit=crop",
        settings: {
          title: "Choose your favorite photos",
          description: "Drag right to keep a photo or left to pass. You can undo any choice.",
          buttonText: "Start selecting",
        },
      },
      card: {
        name: "Card Carousel",
        content:
          "Starter card\nUse this for services, offers, instructions, or dashboard blocks.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&auto=format&fit=crop\n\nSecond card\nRename every title, description, and image from the inspector.\nhttps://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&auto=format&fit=crop",
      },
      carousel: {
        name: "Card Carousel",
        content:
          "Design pages\nBuild flexible page sections and arrange content visually.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1800&q=90&auto=format&fit=crop\n\nCollect responses\nCreate forms and keep structured requests in one workspace.\nhttps://images.unsplash.com/photo-1556761175-b413da4baf72?w=1800&q=90&auto=format&fit=crop\n\nManage operations\nCoordinate reservations, users, and daily work from one place.\nhttps://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1800&q=90&auto=format&fit=crop",
      },
      carouselCards: {
        name: "Card Carousel",
        content:
          "Featured service\nPresent one offer at a time with a clean card and supporting image.\nhttps://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=1200&auto=format&fit=crop\n\nProduct highlight\nUse this variant for offers, collections, packages, or case studies.\nhttps://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&auto=format&fit=crop\n\nCustomer story\nMove through compact slides without taking over the full page section.\nhttps://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1200&auto=format&fit=crop",
      },
      carouselSplit: {
        name: "Split Carousel",
        content:
          "Strategy and execution\nPair focused text with a strong image area for services or announcements.\nhttps://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&auto=format&fit=crop\n\nBuilt for teams\nShow process steps, onboarding, or operational features in a balanced layout.\nhttps://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&auto=format&fit=crop\n\nReady to publish\nUse the same slide format: title, description, and image URL.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&auto=format&fit=crop",
      },
      carouselSpotlight: {
        name: "Spotlight Carousel",
        content:
          "A brighter idea\nPut one bold story in the spotlight with cinematic depth.\nhttps://images.unsplash.com/photo-1497366811353-6870744d04b2?w=1400&auto=format&fit=crop\n\nShape the future\nLayer luminous color, oversized type, and focused imagery.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1400&auto=format&fit=crop\n\nMake it memorable\nChoose a different image for every story directly in the inspector.\nhttps://images.unsplash.com/photo-1556761175-b413da4baf72?w=1400&auto=format&fit=crop",
      },
      carouselStack: {
        name: "Stacked Cards Carousel",
        content:
          "Behind the scenes\nA tactile stack of stories that feels draggable and alive.\nhttps://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1200&auto=format&fit=crop\n\nThe next chapter\nClick the peeking cards or use the controls to move through the stack.\nhttps://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&auto=format&fit=crop\n\nBuilt together\nPerfect for teams, case studies, portfolios, and product collections.\nhttps://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=1200&auto=format&fit=crop",
      },
      carouselEditorial: {
        name: "Editorial Carousel",
        content:
          "Issue No. 01\nAn editorial layout with dramatic numbering and gallery-like composition.\nhttps://images.unsplash.com/photo-1497215842964-222b430dc094?w=1400&auto=format&fit=crop\n\nIssue No. 02\nUse it for campaigns, reports, interviews, or curated project stories.\nhttps://images.unsplash.com/photo-1497366216548-37526070297c?w=1400&auto=format&fit=crop\n\nIssue No. 03\nEvery title, caption, and image remains yours to customize.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1400&auto=format&fit=crop",
      },
      circularGallery: {
        name: "Circular Gallery",
        content:
          "Studio workspace\nA warm workspace for planning and operations.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&auto=format&fit=crop\n\nTeam session\nPeople collaborating around a product launch.\nhttps://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&auto=format&fit=crop\n\nProduct desk\nClean desk scene with business tools.\nhttps://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&auto=format&fit=crop\n\nService meeting\nClient service conversation in progress.\nhttps://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1200&auto=format&fit=crop\n\nAnalytics view\nDashboard and operations review moment.\nhttps://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200&auto=format&fit=crop\n\nLaunch planning\nPlanning board for growth and execution.\nhttps://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&auto=format&fit=crop",
      },
      list: {
        name: "List",
        items: ["First item", "Second item", "Third item"],
      },
      divider: { name: "Divider" },
      thinDivider: { name: "Horizontal Line" },
      embed: {
        name: "Embed",
        content: "https://example.com",
      },
      metric: {
        name: "Metric Group",
        content: "Total Requests\n128",
        metrics: [
          { label: "Total Requests", value: "5,000+", description: "Impactful Reach" },
          { label: "Completed Requests", value: "30+", description: "Programs & Initiatives" },
          { label: "Active Partners", value: "10+", description: "Community Engagement" },
          { label: "Completion Rate", value: "80%", description: "Successful Outcomes" },
        ],
      },
      loginBlock: {
        name: "Login",
        content: "Log in\nAccess your account and continue to your workspace.\nLog in",
        auth: {
          title: "Log in",
          subtitle: "Access your account and continue to your workspace.",
          buttonText: "Log in",
          switchText: "Don't have an account?",
          switchActionText: "Create account",
        },
      },
      registrationBlock: {
        name: "Registration",
        content:
          "Register\nCreate an account to save requests, reservations, and private activity.\nCreate Account",
        auth: {
          title: "Register",
          subtitle: "Create an account to save requests, reservations, and private activity.",
          buttonText: "Create Account",
          switchText: "Already registered?",
          switchActionText: "Log in",
        },
      },
      formBlock: {
        name: "Form Block",
        content: "Connected Form",
      },
      reservationBlock: {
        name: "Reservation",
        content:
          "Book a reservation\nChoose a service, date, and time. We will confirm availability with you.\nConsultation\nService appointment\nTable reservation",
        reservation: {
          title: "Book a reservation",
          description: "Choose a service, date, and time. We will confirm availability with you.",
          services: ["Consultation", "Service appointment", "Table reservation"],
          fields: ["name", "contact", "service", "date", "time", "guests", "notes"],
          submitLabel: "Request reservation",
        },
      },
    },
    structure: {
      column: "Column",
      section: "Section",
      page: "Home",
      workflow: "After form submit",
      workflowSteps: {
        saveResponse: {
          label: "Save response",
          details: "Store submitted values in front-end state.",
        },
        showMessage: {
          label: "Show success message",
          details: "Display the form success message.",
        },
      },
      role: "Viewer",
      user: "Team Member",
      userEmail: "member@example.com",
      userStatus: "Active",
      lastSeen: "Just now",
      project: "Madar App Builder",
    },
  },
  ar: {},
};

export function getFactoryContent(lang = "en") {
  return factoryContent[lang] && Object.keys(factoryContent[lang]).length
    ? factoryContent[lang]
    : factoryContent.en;
}
