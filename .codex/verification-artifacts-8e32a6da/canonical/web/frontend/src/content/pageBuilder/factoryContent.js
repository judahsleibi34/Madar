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
          "Portrait by the window\nNatural light portrait\n\n\nGolden hour walk\nOutdoor couple session\n\n\nQuiet moment\nEditorial wedding detail\n\n\nCelebration\nA candid favorite from the session\n",
        settings: {
          title: "Choose your favorite photos",
          description: "Drag right to keep a photo or left to pass. You can undo any choice.",
          buttonText: "Start selecting",
        },
      },
      card: {
        name: "Card Carousel",
        content:
          "Starter card\nUse this for services, offers, instructions, or dashboard blocks.\n\n\nSecond card\nRename every title, description, and image from the inspector.\n",
      },
      carousel: {
        name: "Card Carousel",
        content:
          "Design pages\nBuild flexible page sections and arrange content visually.\n\n\nCollect responses\nCreate forms and keep structured requests in one workspace.\n\n\nManage operations\nCoordinate reservations, users, and daily work from one place.\n",
      },
      logoSlider: {
        name: "Trusted by leading brands",
        title: "Trusted by leading brands",
        subtitle: "Organizations and teams that choose to work with us.",
        content:
          "Northstar\nPartner\n\nJuniper\nPartner\n\nAtlas\nPartner\n\nMosaic\nPartner\n\nCedar\nPartner",
      },
      carouselCards: {
        name: "Card Carousel",
        content:
          "Featured service\nPresent one offer at a time with a clean card and supporting image.\n\n\nProduct highlight\nUse this variant for offers, collections, packages, or case studies.\n\n\nCustomer story\nMove through compact slides without taking over the full page section.\n",
      },
      carouselSplit: {
        name: "Split Carousel",
        content:
          "Strategy and execution\nPair focused text with a strong image area for services or announcements.\n\n\nBuilt for teams\nShow process steps, onboarding, or operational features in a balanced layout.\n\n\nReady to publish\nUse the same slide format: title, description, and an uploaded image.\n",
      },
      carouselSpotlight: {
        name: "Spotlight Carousel",
        content:
          "A brighter idea\nPut one bold story in the spotlight with cinematic depth.\n\n\nShape the future\nLayer luminous color, oversized type, and focused imagery.\n\n\nMake it memorable\nChoose a different image for every story directly in the inspector.\n",
      },
      carouselStack: {
        name: "Stacked Cards Carousel",
        content:
          "Behind the scenes\nA tactile stack of stories that feels draggable and alive.\n\n\nThe next chapter\nClick the peeking cards or use the controls to move through the stack.\n\n\nBuilt together\nPerfect for teams, case studies, portfolios, and product collections.\n",
      },
      carouselEditorial: {
        name: "Editorial Carousel",
        content:
          "Issue No. 01\nAn editorial layout with dramatic numbering and gallery-like composition.\n\n\nIssue No. 02\nUse it for campaigns, reports, interviews, or curated project stories.\n\n\nIssue No. 03\nEvery title, caption, and image remains yours to customize.\n",
      },
      circularGallery: {
        name: "Circular Gallery",
        content:
          "Studio workspace\nA warm workspace for planning and operations.\n\n\nTeam session\nPeople collaborating around a product launch.\n\n\nProduct desk\nClean desk scene with business tools.\n\n\nService meeting\nClient service conversation in progress.\n\n\nAnalytics view\nDashboard and operations review moment.\n\n\nLaunch planning\nPlanning board for growth and execution.\n",
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
          formItems: [],
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
