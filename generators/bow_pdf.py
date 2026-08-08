"""Locate the official DepEd Budget of Work PDF shipped in references/.

Two trees are covered:
- "Revised K to 10 Curriculum/BUDGET OF WORK" for Kindergarten-Grade 10
  (e.g. "4-G1-Mathematics.pdf", shared TLE files like
  "8-G9-_-G10-TLE_-AFA-Agricultural-Crop-Production.pdf"). Most filenames
  match the app's subject names after normalization; combined files (MAPEH,
  EPP/TLE, shared G9/G10 TLE) need an explicit alias table.
- "Strengthened SHS Program/Curriculum Guides" for Grades 11-12. Tech-pro
  electives live in per-grade "THREE-TERM Grade 11 (BOW)" / "Grade 12 (BOW)"
  folders; academic electives and core subjects are shared three-term guides.
  Subject names differ from the DB names, so an explicit table is used.
"""

import os
import re
import sys


def _resource_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BOW_ROOT = os.path.join(
    _resource_dir(),
    "references",
    "Revised K to 10 Curriculum",
    "BUDGET OF WORK",
)

SSHS_ROOT = os.path.join(
    _resource_dir(),
    "references",
    "Strengthened SHS Program",
    "Curriculum Guides",
)

REFERENCES_ROOT = os.path.join(_resource_dir(), "references")

SSHS_REL = "Strengthened SHS Program/Curriculum Guides"


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _alias_key(grade, subject):
    return (grade, _norm(subject))


# Combined/shared files that do not match the subject name directly.
_ALIAS = {
    ("Kindergarten", "kindergarten"): "1-Kindergarten-BOW.pdf",
    ("Grade 4", "agriculture"): "3-G4-EPP_-AFA-_-FCS-_-IA.pdf",
    ("Grade 4", "homeeconomics"): "3-G4-EPP_-AFA-_-FCS-_-IA.pdf",
    ("Grade 4", "industrialarts"): "3-G4-EPP_-AFA-_-FCS-_-IA.pdf",
    ("Grade 4", "informationandcommunicationstechnologyict"): "4-G4-EPP_-ICT.pdf",
    ("Grade 4", "musicandarts"): "7-G4-MAPEH.pdf",
    ("Grade 4", "peandhealth"): "7-G4-MAPEH.pdf",
    ("Grade 5", "animalproduction"): "3-G5-EPP_-AFA-_-FCS-_-IA.pdf",
    ("Grade 5", "homeeconomics"): "3-G5-EPP_-AFA-_-FCS-_-IA.pdf",
    ("Grade 5", "industrialarts"): "3-G5-EPP_-AFA-_-FCS-_-IA.pdf",
    ("Grade 5", "informationandcommunicationstechnologyict"): "4-G5-EPP_-ICT.pdf",
    ("Grade 5", "musicandarts"): "7-G5-MAPEH.pdf",
    ("Grade 5", "peandhealth"): "7-G5-MAPEH.pdf",
    ("Grade 6", "fisheryarts"): "8-G6-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 6", "homeeconomics"): "8-G6-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 6", "industrialarts"): "8-G6-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 6", "informationandcommunicationstechnologyict"): "9-G6-TLE_-ICT.pdf",
    ("Grade 6", "musicandarts"): "5-G6-MAPEH.pdf",
    ("Grade 6", "peandhealth"): "5-G6-MAPEH.pdf",
    ("Grade 7", "informationandcommunicationstechnologyict"): "8-G7-TLE_-ICT.pdf",
    ("Grade 7", "musicandarts"): "4-G7-MAPEH.pdf",
    ("Grade 7", "peandhealth"): "4-G7-MAPEH.pdf",
    ("Grade 8", "aestheticservicesbeautycare"): "7-G8-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 8", "fisheryarts"): "7-G8-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 8", "foodprocessing"): "7-G8-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 8", "garmentsartisanry"): "7-G8-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 8", "handicraftsweaving"): "7-G8-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 8", "industrialarts"): "7-G8-TLE_-AFA-_-FCS-_-IA.pdf",
    ("Grade 8", "informationandcommunicationstechnologyict"): "8-G8-TLE_-ICT.pdf",
    ("Grade 8", "musicandarts"): "4-G8-MAPEH.pdf",
    ("Grade 8", "peandhealth"): "4-G8-MAPEH.pdf",
    ("Grade 9", "musicandarts"): "4-G9-MAPEH.pdf",
    ("Grade 9", "peandhealth"): "4-G9-MAPEH.pdf",
    ("Grade 10", "musicandarts"): "4-G10-MAPEH.pdf",
    ("Grade 10", "peandhealth"): "4-G10-MAPEH.pdf",
}

# Shared Grade 9/10 TLE files: the same filename lives in both folders.
_SHS_TLE = {
    "agriculturalcropsproduction": "8-G9-_-G10-TLE_-AFA-Agricultural-Crop-Production.pdf",
    "animalproduction": "9-G9-_-G10-TLE_-AFA-Animal-Production.pdf",
    "aquaculture": "10-G9-_-G10-TLE_-AFA-Aquaculture-Fish-Culture.pdf",
    "fishcaptureoperation": "10.5-G9-_-G10-TLE_-AFA-Fish-Capture.pdf",
    "foodprocessing": "11-G9-_-G10-TLE_-AFA-Food-and-Beverage-Processing.pdf",
    "breadandpastryproduction": "13-G9-_-G10-TLE_-FCS-Food-Preparation.pdf",
    "foodandbeverageservices": "14-G9-_-G10-TLE_-FCS-Food-Service.pdf",
    "kitchenoperations": "14-G9-_-G10-TLE_-FCS-Food-Service.pdf",
    "garmentsartisanry": "15-G9-_-G10-TLE_-FCS-Garments.pdf",
    "handicraftsweaving": "16-G9-_-G10-TLE_-FCS-Handicraft.pdf",
    "needlecraft": "16-G9-_-G10-TLE_-FCS-Handicraft.pdf",
    "leathercraft": "16-G9-_-G10-TLE_-FCS-Handicraft.pdf",
    "hairdressingservices": "12-G9-_-G10-TLE_-FCS-Beauty-Care-Services.pdf",
    "nailcareservices": "12-G9-_-G10-TLE_-FCS-Beauty-Care-Services.pdf",
    "wellnessmassage": "17-G9-_-G10-TLE_-FCS-Health-and-Wellness-Massage.pdf",
    "housekeepingservices": "18-G9-_-G10-TLE_-FCS-Hotel-Services.pdf",
    "frontofficeservices": "18-G9-_-G10-TLE_-FCS-Hotel-Services.pdf",
    "tourismservices": "19-G9-_-G10-TLE_-FCS-Tourism-Services.pdf",
    "automotiveservicing": "20-G9-_-G10-TLE_-IA-Automotive-and-Small-Engine-Servicing.pdf",
    "electricalinstallationandmaintenance": "21-G9-_-G10-TLE_-IA-Electrical-and-Electronics-Servicing.pdf",
    "manualmetalarcwelding": "25-G9-_-G10-TLE_-IA-Shielded-Metal-Arc-Welding-SMAW.pdf",
    "masonry": "23-G9-_-G10-TLE_-IA-Residential-Masonry-and-Tile-Setting.pdf",
    "carpentry": "22-G9-_-G10-TLE_-IA-Residential-Carpentry.pdf",
    "plumbing": "24-G9-_-G10-TLE_-IA-Residential-Plumbing.pdf",
    "computersystemsservicing": "27-G9-_-G10-TLE_-ICT-Computer-Systems-Servicing.pdf",
    "computerprogramming": "26-G9-_-G10-TLE_-ICT-Computer-Programming.pdf",
    "telecommunications": "28-G9-_-G10-TLE_-ICT-Telecommunications.pdf",
    "visualarts": "29-G9-_-G10-TLE_-ICT-Visual-Arts.pdf",
}

for _g in ("Grade 9", "Grade 10"):
    for _k, _v in _SHS_TLE.items():
        _ALIAS[(_g, _k)] = _v


# ---- Strengthened SHS Program (Grades 11-12) -------------------------------
# Values are "/"-separated paths relative to SSHS_ROOT.
_CORE = "CORE SUBJECTS"
_ASH = "ACADEMIC ELECTIVES/THREE-TERM/Arts, Social Science, and Humanities Cluster"
_ABM = "ACADEMIC ELECTIVES/THREE-TERM/Business and Entrepreneurship Cluster"
_FEX = "ACADEMIC ELECTIVES/THREE-TERM/Field Experience"
_STEM = "ACADEMIC ELECTIVES/THREE-TERM/Science, Technology, Engineering, and Mathematics Cluster"
_SPOR = "ACADEMIC ELECTIVES/THREE-TERM/Sports, Health, and Wellness Cluster"
_T11 = "TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)"
_T12 = "TECH-PRO ELECTIVES/THREE-TERM Grade 12 (BOW)"

_SSHS = {
    # Core subjects (Grade 11)
    ("Grade 11", "generalmathematicssshs"): _CORE + "/General-Mathematics-2.pdf",
    ("Grade 11", "generalscience"): _CORE + "/General-Science-2.pdf",
    ("Grade 11", "lifeandcareerskills"): _CORE + "/Life-and-Career-Skills-2.pdf",
    ("Grade 11", "pagaaralngkasaysayanatlipunangpilipino"): _CORE + "/Pag-aaral-ng-Kasaysayan-at-Lipunang-Pilipino-2.pdf",
    ("Grade 11", "effectivecommunicationfilipinoandenglish"): _CORE + "/Effective-Communication-2.pdf",
    # Grade 11 academic electives - Arts, Social Science, Humanities
    ("Grade 11", "contemporaryliterature1"): _ASH + "/Contemporary-Literature-1-2.pdf",
    ("Grade 11", "contemporaryliterature2"): _ASH + "/Contemporary-Literature-2-2.pdf",
    ("Grade 11", "creativecomposition1"): _ASH + "/Creative-Composition-1-2.pdf",
    ("Grade 11", "creativecomposition2"): _ASH + "/Creative-Composition-2-2.pdf",
    ("Grade 11", "introductiontophilosophy"): _ASH + "/Introduction-to-the-Philosophy-of-Human-Person.pdf",
    ("Grade 11", "malikhaingpagsulat"): _ASH + "/Malikhaing-Pagsulat-Updated-as-of-060526.pdf",
    ("Grade 11", "filipino1wikaatkomunikasyonsaakademikongfilipino"): _ASH + "/Filipino-1-Wika-at-Komunikasyon-sa-Akademikong-Filipino-Updated-as-of-060526.pdf",
    ("Grade 11", "creativeindustriesappliedandtraditionalarts"): _ASH + "/Creative-Industries-Applied-and-Traditional-Arts.pdf",
    ("Grade 11", "creativeindustriesdance"): _ASH + "/Creative-Industries-Dance.pdf",
    ("Grade 11", "creativeindustriesliteraryarts"): _ASH + "/Creative-Industries-Literary-Arts.pdf",
    ("Grade 11", "creativeindustriesmediaarts"): _ASH + "/Creative-Industries-Media-Arts.pdf",
    ("Grade 11", "creativeindustriesmusic"): _ASH + "/Creative-Industries-Music.pdf",
    ("Grade 11", "creativeindustriestheaterarts"): _ASH + "/Creative-Industries-Theater-Arts.pdf",
    ("Grade 11", "creativeindustriesvisualarts"): _ASH + "/Creative-Industries-Visual-Arts.pdf",
    ("Grade 11", "filipinoidentitythroughthearts"): _ASH + "/Filipino-Identity-Through-the-Arts-Updated-as-of-060526.pdf",
    ("Grade 11", "leadershipandmanagementinthearts"): _ASH + "/Leadership-and-Management-in-the-Arts-Updated-as-of-060526.pdf",
    ("Grade 11", "artcriticismandcreativemarkets"): _ASH + "/Art-Criticism-and-Creative-Markets.pdf",
    ("Grade 11", "performancecriticismandcreativemarkets"): _ASH + "/Performance-Criticism-and-Creative-Markets.pdf",
    # Grade 11 academic electives - Business and Entrepreneurship
    ("Grade 11", "business1basicaccounting"): _ABM + "/Business-1-Basic-Accounting-2.pdf",
    ("Grade 11", "business2businessfinanceandincometaxation"): _ABM + "/Business-2-Business-Finance-and-Income-Taxation-2.pdf",
    ("Grade 11", "introductiontoorganizationandmanagement"): _ABM + "/Introduction-to-Organization-and-Management-2.pdf",
    # Grade 11 academic electives - STEM
    ("Grade 11", "biology1"): _STEM + "/Biology-1-2.pdf",
    ("Grade 11", "biology2"): _STEM + "/Biology-2-2.pdf",
    ("Grade 11", "chemistry1"): _STEM + "/Chemistry-1-Updated-as-of-060526.pdf",
    ("Grade 11", "chemistry2"): _STEM + "/Chemistry-2-Updated-as-of-073026.pdf",
    ("Grade 11", "physics1"): _STEM + "/Physics-1-2.pdf",
    ("Grade 11", "physics2"): _STEM + "/Physics-2-2.pdf",
    ("Grade 11", "earthandspacescience1"): _STEM + "/Earth-and-Space-Science-1-2.pdf",
    ("Grade 11", "earthandspacescience2"): _STEM + "/Earth-and-Space-Science-2-2.pdf",
    ("Grade 11", "finitemathematics1"): _STEM + "/Finite-Mathematics-1-2.pdf",
    ("Grade 11", "finitemathematics2"): _STEM + "/Finite-Mathematics-2-2.pdf",
    # Grade 11 academic electives - Sports
    ("Grade 11", "humanmovement1basicanatomyinsportsandexercise"): _SPOR + "/Human-Movement-1-Basic-Anatomy-in-Sports-and-Exercise-Updated-as-of-060526.pdf",
    ("Grade 11", "humanmovement2motorskillsdevelopment"): _SPOR + "/Human-Movement-2-Motor-Skills-Development-Updated-as-of-060526.pdf",
    ("Grade 11", "physicaleducation1fitnessandrecreation"): _SPOR + "/Physical-Education-1-Fitness-and-Recreation-2.pdf",
    ("Grade 11", "physicaleducation2sportsanddance"): _SPOR + "/Physical-Education-2-Sports-and-Dance-2.pdf",
    ("Grade 11", "sportscoaching1"): _SPOR + "/Sports-Coaching-2.pdf",
    ("Grade 11", "sportsofficiating1"): _SPOR + "/Sports-Officiating-2.pdf",
    # Grade 11 tech-pro electives
    ("Grade 11", "aestheticservicesbeautycare"): _T11 + "/Aesthetic, Wellness, and Human Care/G11-Aesthetic-Services-Beauty-Care-1.pdf",
    ("Grade 11", "caregivingadultcare"): _T11 + "/Aesthetic, Wellness, and Human Care/G11-Caregiving-Adult-Care-1.pdf",
    ("Grade 11", "caregivingchildcare"): _T11 + "/Aesthetic, Wellness, and Human Care/G11-Caregiving-Child-Care-1.pdf",
    ("Grade 11", "hairdressingservices"): _T11 + "/Aesthetic, Wellness, and Human Care/G11-Hairdressing-Services-1.pdf",
    ("Grade 11", "agriculturalcropsproduction"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Agricultural-Crops-Production-1.pdf",
    ("Grade 11", "agroentrepreneurship"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Agro-Entrepreneurship-1.pdf",
    ("Grade 11", "aquaculture"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Aquaculture-1.pdf",
    ("Grade 11", "fishcaptureoperation"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Fish-Capture-Operation-1.pdf",
    ("Grade 11", "foodprocessing"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Food-Processing-1.pdf",
    ("Grade 11", "organicagricultureproduction"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Organic-Agriculture-Production-1-1.pdf",
    ("Grade 11", "poultryproductionchicken"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Poultry-Production-Chicken-1.pdf",
    ("Grade 11", "ruminantsproduction"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Ruminants-Production-1.pdf",
    ("Grade 11", "swineproduction"): _T11 + "/Agri-Fishery Business and Food Innovation/G11-Swine-Production-1.pdf",
    ("Grade 11", "garmentsartisanry"): _T11 + "/Artisanry and Creative Enterprise/G11-Garments-Artisanry.pdf",
    ("Grade 11", "handicraftsweaving"): _T11 + "/Artisanry and Creative Enterprise/G11-Handicrafts_-Weaving.pdf",
    ("Grade 11", "drivingandautomotiveservicing"): _T11 + "/Automotive and Small Engine Technologies/G11-Driving-and-Automotive-Servicing-1.pdf",
    ("Grade 11", "motorcycleandsmallengineservicing"): _T11 + "/Automotive and Small Engine Technologies/G11-Motorcycle-and-Small-Engine-Servicing-1-1.pdf",
    ("Grade 11", "carpentry"): _T11 + "/Construction and Building Technology/G11-Carpentry-1.pdf",
    ("Grade 11", "constructionoperation"): _T11 + "/Construction and Building Technology/G11-Construction-Operation-1.pdf",
    ("Grade 11", "manualmetalarcwelding"): _T11 + "/Construction and Building Technology/G11-Manual-Metal-Arc-Welding-1.pdf",
    ("Grade 11", "technicaldrafting"): _T11 + "/Construction and Building Technology/G11-Technical-Drafting-1.pdf",
    ("Grade 11", "animation"): _T11 + "/Creative Arts and Design Technology/G11-Animation-Updated-as-of-07.31.26.pdf",
    ("Grade 11", "illustration"): _T11 + "/Creative Arts and Design Technology/G11-Illustration-.pdf",
    ("Grade 11", "visualgraphicdesign"): _T11 + "/Creative Arts and Design Technology/G11-Visual-Graphic-Design.pdf",
    ("Grade 11", "bakeryoperations"): _T11 + "/Hospitality and Tourism/G11-Bakery-Operations.pdf",
    ("Grade 11", "eventmanagementservices"): _T11 + "/Hospitality and Tourism/G11-Event-Management-Services.pdf",
    ("Grade 11", "foodandbeverageoperations"): _T11 + "/Hospitality and Tourism/G11-Food-and-Beverage-Operation.pdf",
    ("Grade 11", "hospitalityoperationsfrontofficeservices"): _T11 + "/Hospitality and Tourism/G11-Hotel-Operations-Front-Office-Services.pdf",
    ("Grade 11", "hospitalityoperationshousekeepingservices"): _T11 + "/Hospitality and Tourism/G11-Hotel-Operations-Housekeeping-Services.pdf",
    ("Grade 11", "kitchenoperations"): _T11 + "/Hospitality and Tourism/G11-Kitchen-Operations.pdf",
    ("Grade 11", "tourismservices"): _T11 + "/Hospitality and Tourism/G11-Tourism-Services.pdf",
    ("Grade 11", "broadbandinstallation"): _T11 + "/ICT Support and Computer Programming Technologies/G11-Broadband-Installation.pdf",
    ("Grade 11", "computerprogrammingnettechnology"): _T11 + "/ICT Support and Computer Programming Technologies/G11-Computer-Programming-.Net-Technology.pdf",
    ("Grade 11", "computerprogrammingjava"): _T11 + "/ICT Support and Computer Programming Technologies/G11-Computer-Programming-Java.pdf",
    ("Grade 11", "computerprogrammingoracledatabase"): _T11 + "/ICT Support and Computer Programming Technologies/G11-Computer-Programming-Oracle-Database.pdf",
    ("Grade 11", "computersystemsservicing"): _T11 + "/ICT Support and Computer Programming Technologies/G11-Computer-Systems-Servicing.pdf",
    ("Grade 11", "contactcenterservices"): _T11 + "/ICT Support and Computer Programming Technologies/G11-Contact-Center-Services.pdf",
    ("Grade 11", "domesticrefrigerationandairconditioningservicing"): _T11 + "/Industrial Technologies/G11-Domestic-Refrigeration-and-Air-Conditioning-Servic.pdf",
    ("Grade 11", "electricalinstallationandmaintenance"): _T11 + "/Industrial Technologies/G11-Electrical-Installation-and-Maintenance.pdf",
    ("Grade 11", "electronicproductsassemblyandservicing"): _T11 + "/Industrial Technologies/G11-Electronic-Products-Assembly-and-Servicing-.pdf",
    ("Grade 11", "photovoltaicsystemsinstallation"): _T11 + "/Industrial Technologies/G11-Photovoltaic-Systems-Installation.pdf",
    ("Grade 11", "maritimeengineeringatthesupportlevel"): _T11 + "/Maritime/G11-Maritime-Engineering-at-the-Support-Level.docx.pdf",
    ("Grade 11", "maritimetransportationatthesupportlevel"): _T11 + "/Maritime/G11-Maritime-Transportation-at-the-Support-Level.pdf",
    ("Grade 11", "shipscateringservices"): _T11 + "/Maritime/G11-Ships-Catering-Services.pdf",
    # Grade 12 academic electives - STEM
    ("Grade 12", "biology3"): _STEM + "/Biology-3-1.pdf",
    ("Grade 12", "biology4"): _STEM + "/Biology-4-1.pdf",
    ("Grade 12", "chemistry3"): _STEM + "/Chemistry-3-1.pdf",
    ("Grade 12", "chemistry4"): _STEM + "/Chemistry-4-1.pdf",
    ("Grade 12", "physics3"): _STEM + "/Physics-3-1.pdf",
    ("Grade 12", "physics4"): _STEM + "/Physics-4-1.pdf",
    ("Grade 12", "earthandspacescience3"): _STEM + "/Earth-and-Space-Science-3-1.pdf",
    ("Grade 12", "earthandspacescience4"): _STEM + "/Earth-and-Space-Science-4-1.pdf",
    ("Grade 12", "advancedmathematics"): _STEM + "/Advanced-Mathematics-Updated-as-of-05.29.26.pdf",
    ("Grade 12", "basiccalculus"): _STEM + "/Basic-Calculus-Updated-as-of-05.29.26.pdf",
    ("Grade 12", "precalculus"): _STEM + "/Pre-Calculus-1.pdf",
    ("Grade 12", "databasemanagement"): _STEM + "/Database-Management-Updated-as-of-05.29.26-.pdf",
    ("Grade 12", "fundamentalsofdataanalytics"): _STEM + "/Fundamentals-of-Data-Analytics-Updated-as-of-05.29.26.pdf",
    ("Grade 12", "empowermenttechnologies"): _STEM + "/Empowerment-Technologies-Updated-as-of-05.29.26-.pdf",
    ("Grade 12", "conceptualphysicsandchemistryindailylife"): _STEM + "/Conceptual-Physics-and-Chemistry-in-Daily-Life-Updated-as-of-05.29.26.pdf",
    ("Grade 12", "conceptualbiologyandearthandspacescience"): _STEM + "/Conceptual-Biology-and-Earth-and-Space-Science-Updated-as-of-05.29.26.pdf",
    # Grade 12 academic electives - Arts, Social Science, Humanities
    ("Grade 12", "introductiontothephilosophyofthehumanperson"): _ASH + "/Introduction-to-the-Philosophy-of-Human-Person.pdf",
    ("Grade 12", "philippinegovernancephilippinepoliticsandgovernance"): _ASH + "/Philippine-Governance-Philippine-Politics-and-Governance-Updated-as-of-060526.pdf",
    ("Grade 12", "socialsciencestheoryandpractice"): _ASH + "/Social-Sciences-Theory-and-Practice-Updated-as-of-060526.pdf",
    ("Grade 12", "citizenshipandcivicengagement"): _ASH + "/Citizenship-and-Civic-Engagement-Updated-as-of-060526.pdf",
    ("Grade 12", "filipino2filipinosaisports"): _ASH + "/Filipino-2-Filipino-sa-Isports-Updated-as-of-060526.pdf",
    ("Grade 12", "filipino2filipinoparasalarangteknikalpropesyonal"): _ASH + "/Filipino-2-Filipino-sa-Larang-Teknikal-Propesyonal-Updated-as-of-060526.pdf",
    ("Grade 12", "filipino2filipinosasiningatdisenyo"): _ASH + "/Filipino-2-Filipino-sa-Sining-at-Disenyo-Updated-as-of-060526.pdf",
    ("Grade 12", "creativeproductionandpresentation"): _ASH + "/Creative-Production-and-Presentation-1.pdf",
    # Grade 12 academic electives - Business and Entrepreneurship
    ("Grade 12", "business3businesseconomics"): _ABM + "/Business-3-Business-Economics-2.pdf",
    ("Grade 12", "contemporarymarketing"): _ABM + "/Contemporary-Marketing.pdf",
    ("Grade 12", "entrepreneurship"): _ABM + "/Entrepreneurship-2.pdf",
    # Grade 12 academic electives - Sports
    ("Grade 12", "sportscoaching2"): _SPOR + "/Sports-Coaching-2.pdf",
    ("Grade 12", "sportsofficiating2"): _SPOR + "/Sports-Officiating-2.pdf",
    ("Grade 12", "sportsactivitymanagement"): _SPOR + "/Sports-Activity-Management-Updated-as-of-060526.pdf",
    ("Grade 12", "firstaid"): _SPOR + "/First-Aid-1.pdf",
    ("Grade 12", "fundamentalsofbasiclifesupport"): _SPOR + "/Fundamentals-of-Basic-Life-Support-1.pdf",
    ("Grade 12", "exerciseandsportsprogramming"): _SPOR + "/Exercise-and-Sports-Programming-1.pdf",
    # Grade 12 work immersion (field experience)
    ("Grade 12", "designandinnovation"): _FEX + "/Design-and-Innovation.pdf",
    ("Grade 12", "incampusfieldexposureforsports"): _FEX + "/In-Campus-Field-Exposure-for-Sports-.pdf",
    ("Grade 12", "research1"): _FEX + "/Research-1-1.pdf",
    ("Grade 12", "research2"): _FEX + "/Research-2-1.pdf",
    ("Grade 12", "artsapprenticeshipdance"): _FEX + "/Arts-Apprenticeship---Dance.pdf",
    ("Grade 12", "artsapprenticeshipliteraryarts"): _FEX + "/Arts-Apprenticeship-Literary-Arts-1.pdf",
    ("Grade 12", "artsapprenticeshipmediaarts"): _FEX + "/Arts-Apprenticeship-Media-Arts-1.pdf",
    ("Grade 12", "artsapprenticeshipmusic"): _FEX + "/Arts-Apprenticeship---Music-.pdf",
    ("Grade 12", "artsapprenticeshiptheaterarts"): _FEX + "/Arts-Apprenticeship---Theater-Arts-.pdf",
    ("Grade 12", "artsapprenticeshiptraditionalculturalexpressions"): _FEX + "/Arts-Apprenticeship---Traditional-Cultural-Expressions-.pdf",
    ("Grade 12", "artsapprenticeshipvisualarts"): _FEX + "/Arts-Apprenticeship---Visual-Arts.pdf",
    # Grade 12 tech-pro electives
    ("Grade 12", "aestheticservicesbeautycare"): _T12 + "/Aesthetic, Wellness, and Human Care/G12-Aesthetic-Services-Beauty-Care-1.pdf",
    ("Grade 12", "caregivingadultcare"): _T12 + "/Aesthetic, Wellness, and Human Care/G12-Caregiving-Adult-Care-1.pdf",
    ("Grade 12", "caregivingchildcare"): _T12 + "/Aesthetic, Wellness, and Human Care/G12-Caregiving-Child-Care-1.pdf",
    ("Grade 12", "hairdressingservices"): _T12 + "/Aesthetic, Wellness, and Human Care/G12-Hairdressing-Services-1.pdf",
    ("Grade 12", "agriculturalcropsproduction"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Agricultural-Crops-Production-1.pdf",
    ("Grade 12", "agroentrepreneurship"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Agro-Entrepreneurship-1.pdf",
    ("Grade 12", "aquaculture"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Aquaculture-1.pdf",
    ("Grade 12", "fishcaptureoperation"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Fish-Capture-Operation-1.pdf",
    ("Grade 12", "foodprocessing"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Food-Processing-1.pdf",
    ("Grade 12", "organicagricultureproduction"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Organic-Agriculture-Production-1.pdf",
    ("Grade 12", "poultryproductionchicken"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Poultry-Production-Chicken-1.pdf",
    ("Grade 12", "ruminantsproduction"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Ruminants-Production-1.pdf",
    ("Grade 12", "swineproduction"): _T12 + "/Agri-Fishery Business and Food Innovation/G12-Swine-Production-1.pdf",
    ("Grade 12", "garmentsartisanry"): _T12 + "/Artisanry and Creative Enterprise/G12-Garments-Artisanry.pdf",
    ("Grade 12", "handicraftsweaving"): _T12 + "/Artisanry and Creative Enterprise/G12-Handicrafts_-Weaving.pdf",
    ("Grade 12", "automotiveservicingelectricalrepair"): _T12 + "/Automotive and Small Engine Technologies/G12-Automotive-Servicing-Electrical-Repair-1-1.pdf",
    ("Grade 12", "automotiveservicingengineandchassisrepairs"): _T12 + "/Automotive and Small Engine Technologies/G12-Automotive-Servicing-Engine-and-Chassis-Repairs-1.pdf",
    ("Grade 12", "drivingandautomotiveservicing"): _T12 + "/Automotive and Small Engine Technologies/G12-Driving-And-Automotive-Servicing-2.pdf",
    ("Grade 12", "motorcycleandsmallengineservicing"): _T12 + "/Automotive and Small Engine Technologies/G12-Motorcycle-And-Small-Engine-Servicing.docx-1.pdf",
    ("Grade 12", "carpentry"): _T12 + "/Construction and Building Technology/G12-Carpentry-1.pdf",
    ("Grade 12", "constructionoperation"): _T12 + "/Construction and Building Technology/G12-Construction-Operation-1.pdf",
    ("Grade 12", "manualmetalarcwelding"): _T12 + "/Construction and Building Technology/G12-Manual-Metal-Arc-Welding-1.pdf",
    ("Grade 12", "technicaldrafting"): _T12 + "/Construction and Building Technology/G12-Technical-Drafting-1.pdf",
    ("Grade 12", "animation"): _T12 + "/Creative Arts and Design Technology/G12-Animation-Updated-as-of-07.31.26.pdf",
    ("Grade 12", "illustration"): _T12 + "/Creative Arts and Design Technology/G12-Illustration-.pdf",
    ("Grade 12", "visualgraphicdesign"): _T12 + "/Creative Arts and Design Technology/G12-Visual-Graphic-Design-1.pdf",
    ("Grade 12", "bakeryoperations"): _T12 + "/Hospitality and Tourism/G12-Bakery-Operations-1.pdf",
    ("Grade 12", "eventmanagementservices"): _T12 + "/Hospitality and Tourism/G12-Event-Management-Services.pdf",
    ("Grade 12", "foodandbeverageoperations"): _T12 + "/Hospitality and Tourism/G12-Food-and-Beverage-Operations.pdf",
    ("Grade 12", "hospitalityoperationsfrontofficeservices"): _T12 + "/Hospitality and Tourism/G12-Hospitality-Operations-Front-Office-Services.pdf",
    ("Grade 12", "hospitalityoperationshousekeepingservices"): _T12 + "/Hospitality and Tourism/G12-Hospitality-Operations-Housekeeping-Services.pdf",
    ("Grade 12", "kitchenoperations"): _T12 + "/Hospitality and Tourism/G12-Kitchen-Operations-1.pdf",
    ("Grade 12", "tourismservices"): _T12 + "/Hospitality and Tourism/G12-Tourism-Services-1.pdf",
    ("Grade 12", "broadbandinstallation"): _T12 + "/ICT Support and Computer Programming Technologies/G12-Broadband-Installation.pdf",
    ("Grade 12", "computerprogrammingnettechnology"): _T12 + "/ICT Support and Computer Programming Technologies/G12-Computer-Programming.Net-Technology.pdf",
    ("Grade 12", "computerprogrammingjava"): _T12 + "/ICT Support and Computer Programming Technologies/G12-Computer-Programming-Java-1.pdf",
    ("Grade 12", "computerprogrammingoracledatabase"): _T12 + "/ICT Support and Computer Programming Technologies/G12-Computer-Programming-Oracle-Database-1.pdf",
    ("Grade 12", "computersystemsservicing"): _T12 + "/ICT Support and Computer Programming Technologies/G12-Computer-Systems-Servicing-1.pdf",
    ("Grade 12", "contactcenterservices"): _T12 + "/ICT Support and Computer Programming Technologies/G12-Contact-Center-Services-1.pdf",
    ("Grade 12", "commercialairconditioninginstallationandservicing"): _T12 + "/Industrial Technologies/G12-Commercial-Air-Conditioning-Installation-And-Servi.pdf",
    ("Grade 12", "domesticrefrigerationandairconditioningservicing"): _T12 + "/Industrial Technologies/G12-Domestic-Refrigeration-And-Air-Conditioning-Servicing-1.pdf",
    ("Grade 12", "electricalinstallationandmaintenance"): _T12 + "/Industrial Technologies/G12-Electrical-Installation-And-Maintenance-1.pdf",
    ("Grade 12", "electronicproductsassemblyandservicing"): _T12 + "/Industrial Technologies/G12-Electronic-Products-Assembly-And-Servicing-1.pdf",
    ("Grade 12", "mechatronics"): _T12 + "/Industrial Technologies/G12-Mechatronics.pdf",
    ("Grade 12", "photovoltaicsystemsinstallation"): _T12 + "/Industrial Technologies/G12-Photovoltaic-Systems-Installation-1.pdf",
    ("Grade 12", "maritimeengineeringatthesupportlevel"): _T12 + "/Maritime/G12-Maritime-Engineering-at-the-Support-Level-.pdf",
    ("Grade 12", "maritimetransportationatthesupportlevel"): _T12 + "/Maritime/G12-Maritime-Transportation-at-the-Support-Level.docx.pdf",
    ("Grade 12", "shipscateringservices"): _T12 + "/Maritime/G12-Ships-Catering-Services-1.pdf",
}

# ---- Cross-grade official docs ---------------------------------------------
# DepEd ships no BoW PDF in the Grade 7 / Grade 9 / Grade 10 folders for some
# TLE tracks. These point to the official BoW of the same strand published at
# the nearest grade level (values are "/"-separated paths relative to
# REFERENCES_ROOT).
_K10_BOW = "Revised K to 10 Curriculum/BUDGET OF WORK"
_K10_CG = "Revised K to 10 Curriculum/CURRICULUM GUIDES"

_LINK = {
    # Grade 7 exploratory TLE -> shared official Grade 9/10 track BoW
    ("Grade 7", "agriculturalcropsproduction"): _K10_BOW + "/Grade 9/8-G9-_-G10-TLE_-AFA-Agricultural-Crop-Production.pdf",
    ("Grade 7", "animalproduction"): _K10_BOW + "/Grade 9/9-G9-_-G10-TLE_-AFA-Animal-Production.pdf",
    ("Grade 7", "foodandbeverageservices"): _K10_BOW + "/Grade 9/14-G9-_-G10-TLE_-FCS-Food-Service.pdf",
    ("Grade 7", "tourismservices"): _K10_BOW + "/Grade 9/19-G9-_-G10-TLE_-FCS-Tourism-Services.pdf",
    ("Grade 7", "industrialarts"): _K10_CG + "/3-FINAL-MATATAG-EPP_TLE-CG-2023-Grades-4-10.pdf",
    # Grade 9/10 tech-voc strands -> official SSHS Grade 11 BoW for the same track
    ("Grade 9", "animation"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Creative Arts and Design Technology/G11-Animation-Updated-as-of-07.31.26.pdf",
    ("Grade 9", "caregiving"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Aesthetic, Wellness, and Human Care/G11-Caregiving-Adult-Care-1.pdf",
    ("Grade 9", "contactcenterservices"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/ICT Support and Computer Programming Technologies/G11-Contact-Center-Services.pdf",
    ("Grade 9", "domesticrefrigerationandairconditioningservicing"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Industrial Technologies/G11-Domestic-Refrigeration-and-Air-Conditioning-Servic.pdf",
    ("Grade 9", "illustration"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Creative Arts and Design Technology/G11-Illustration-.pdf",
    ("Grade 9", "poultryproductionchicken"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Agri-Fishery Business and Food Innovation/G11-Poultry-Production-Chicken-1.pdf",
    ("Grade 9", "ruminantsproduction"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Agri-Fishery Business and Food Innovation/G11-Ruminants-Production-1.pdf",
    ("Grade 9", "swineproduction"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Agri-Fishery Business and Food Innovation/G11-Swine-Production-1.pdf",
    ("Grade 10", "animation"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Creative Arts and Design Technology/G11-Animation-Updated-as-of-07.31.26.pdf",
    ("Grade 10", "caregiving"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Aesthetic, Wellness, and Human Care/G11-Caregiving-Adult-Care-1.pdf",
    ("Grade 10", "contactcenterservices"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/ICT Support and Computer Programming Technologies/G11-Contact-Center-Services.pdf",
    ("Grade 10", "domesticrefrigerationandairconditioningservicing"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Industrial Technologies/G11-Domestic-Refrigeration-and-Air-Conditioning-Servic.pdf",
    ("Grade 10", "illustration"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Creative Arts and Design Technology/G11-Illustration-.pdf",
    ("Grade 10", "poultryproductionchicken"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Agri-Fishery Business and Food Innovation/G11-Poultry-Production-Chicken-1.pdf",
    ("Grade 10", "ruminantsproduction"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Agri-Fishery Business and Food Innovation/G11-Ruminants-Production-1.pdf",
    ("Grade 10", "swineproduction"): SSHS_REL + "/TECH-PRO ELECTIVES/THREE-TERM Grade 11 (BOW)/Agri-Fishery Business and Food Innovation/G11-Swine-Production-1.pdf",
}

# Additional official DepEd files bundled with a subject's BoW (e.g. the
# Kindergarten Learning Delivery Guide that ships next to its BoW). Values are
# "/"-relative paths under REFERENCES_ROOT.
_EXTRA = {
    ("Kindergarten", "kindergarten"): [
        _K10_BOW + "/Kindergarten/2-Kindergarten-Learning-Delivery-Guide.pdf",
    ],
}


def find_bow_extras(grade, subject):
    """Resolve the extra official PDFs bundled with (grade, subject)."""
    if not grade or not subject:
        return []
    paths = []
    for rel in _EXTRA.get(_alias_key(grade, subject), []):
        p = _resolve_rel(rel, REFERENCES_ROOT)
        if p:
            paths.append(p)
    return paths


def _folder_pdfs(grade):
    folder = os.path.join(BOW_ROOT, grade)
    if not os.path.isdir(folder):
        return []
    try:
        return [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    except OSError:
        return []


def _resolve_rel(rel, root):
    """Resolve a "/" relative path under `root`, tolerating dash variants.

    Some shipped filenames use an en dash (U+2013) where the table has ASCII
    hyphens; fall back to a normalized name match inside the parent folder.
    """
    path = os.path.join(root, *rel.split("/"))
    if os.path.isfile(path):
        return path
    folder, name = os.path.split(path)
    wanted = _norm(os.path.splitext(name)[0])
    if not wanted or not os.path.isdir(folder):
        return None
    try:
        for f in os.listdir(folder):
            if f.lower().endswith(".pdf") and _norm(os.path.splitext(f)[0]) == wanted:
                return os.path.join(folder, f)
    except OSError:
        pass
    return None


def find_bow_pdf(grade, subject):
    """Absolute path to the official BoW PDF for (grade, subject), or None."""
    if not grade or not subject:
        return None
    # Cross-grade official docs for TLE tracks DepEd did not ship at this grade.
    rel = _LINK.get(_alias_key(grade, subject))
    if rel:
        return _resolve_rel(rel, REFERENCES_ROOT)
    # Strengthened SHS (Grades 11-12): explicit path table under SSHS_ROOT.
    if grade in ("Grade 11", "Grade 12"):
        rel = _SSHS.get(_alias_key(grade, subject))
        return _resolve_rel(rel, SSHS_ROOT) if rel else None
    wanted = _ALIAS.get(_alias_key(grade, subject))
    if not wanted:
        key = _norm(subject)
        if not key:
            return None
        candidates = [
            f for f in _folder_pdfs(grade)
            if _norm(os.path.splitext(f)[0]) == key
            or _norm(os.path.splitext(f)[0]).endswith(key)
        ]
        if not candidates:
            return None
        # Prefer exact normalized-name matches first, then a filename without a
        # duplicate suffix (e.g. "6-G7-Science.pdf" over "6-G7-Science (1).pdf").
        candidates.sort(key=lambda f: (
            _norm(os.path.splitext(f)[0]) != key, " (" in f
        ))
        wanted = candidates[0]
    path = os.path.join(BOW_ROOT, grade, wanted)
    return path if os.path.isfile(path) else None


def bow_pdf_filename(grade, subject):
    path = find_bow_pdf(grade, subject)
    return os.path.basename(path) if path else None
