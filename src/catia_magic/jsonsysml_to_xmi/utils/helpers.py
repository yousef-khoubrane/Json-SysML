
import json
import uuid
from lxml import etree

def gen_id():
    return "_" + str(uuid.uuid4()).replace("-", "")

def parse_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_xmi_template(xmi_path):
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xmi_path, parser)
    return tree

def update_nsmap(tree, namespaces):
    old_root = tree.getroot()
    nsmap = old_root.nsmap.copy()
    nsmap.update(namespaces)
    new_root = etree.Element(
        old_root.tag,
        nsmap=nsmap
    )
    new_root.attrib.update(old_root.attrib)
    for child in old_root:
        new_root.append(child)
    new_root.text = old_root.text
    tree._setroot(new_root)

def smart_uncast(value):
    if isinstance(value, dict):
        return value.get("idref")
    elif isinstance(value, bool):
        return "true" if value else "false"
    return str(value)

namespaces = {
    "xmi": "http://www.omg.org/spec/XMI/20131001",
    "uml": "http://www.omg.org/spec/UML/20131001",
    "sysml": "http://www.omg.org/spec/SysML/20181001/SysML",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "Stereotypes": "http://www.magicdraw.com/schemas/Stereotypes.xmi",
    "DSL_Customization": "http://www.magicdraw.com/schemas/DSL_Customization.xmi",
    "Validation_Profile": "http://www.magicdraw.com/schemas/Validation_Profile.xmi",
    "MagicDraw_Profile": "http://www.omg.org/spec/UML/20131001/MagicDrawProfile",
    "Dependency_Matrix_Profile": "http://www.magicdraw.com/schemas/Dependency_Matrix_Profile.xmi",
    "MD_Customization_for_SysML__additional_stereotypes": "http://www.magicdraw.com/spec/Customization/180/SysML",
    "MD_Customization_for_Requirements__additional_stereotypes": "http://www.magicdraw.com/spec/Customization/180/Requirements",
    "StandardProfile": "http://www.omg.org/spec/UML/20131001/StandardProfile"
}
# The same XMI file may use different namespaces, so we define an alternative set. Add more if needed.
alt_namespaces = {
    "xmi": "http://www.omg.org/XMI"
}
all_ns = [namespaces]
for key, value in alt_namespaces.items():
    new_ns = namespaces.copy()
    new_ns[key] = value
    if new_ns not in all_ns:
        all_ns.append(new_ns)

diagram_full_types = {
    "act": "SysML Activity Diagram",
    "bdd": "SysML Block Definition Diagram",
    "ibd": "SysML Internal Block Diagram",
    "par": "SysML Parametric Diagram",
    "pkg": "SysML Package Diagram",
    "req": "Requirement Diagram",
    "sd": "SysML Sequence Diagram",
    "stm": "SysML State Machine Diagram",
    "uc": "SysML Use Case Diagram",
}

diagram_uml_types = {
    "act": "Activity Diagram",
    "bdd": "Class Diagram",
    "ibd": "Composite Structure Diagram",
    "par": "Composite Structure Diagram",
    "pkg": "Class Diagram",
    "req": "Class Diagram",
    "sd": "Sequence Diagram",
    "stm": "State Machine Diagram",
    "uc": "Use Case Diagram",
}

def get_diagram_required_features(diagram_type):
    if diagram_type == "req":
        return "com.nomagic.requirements#Cameo Requirements Modeler;UML_Standard_Profile.mdzip;MD Customization for Requirements.mdzip"
    return "com.nomagic.magicdraw.plugins.impl.sysml#SysML;MD_customization_for_SysML.mdzip;UML_Standard_Profile.mdzip"

predefined_types = ["String", "Real", "Number", "Complex", "Integer", "Boolean", "VerdictKind", "void"]
def get_predefined_type_info(type):
    if type == "void":
        return {
            "href": "UML_Standard_Profile.mdzip#eee_1045467100323_249638_60",
            "referenceExtension_attributes": {
                "referentPath": "UML Standard Profile::MagicDraw Profile::datatypes::void",
                "referentType": "DataType"
            }
        }
    elif type == "VerdictKind":
        return {
            "href": "http://www.omg.org/spec/SysML/20181001/SysML.xmi#SysML_dataType.VerdictKind",
            "referenceExtension_attributes": {
                "referentPath": f"SysML::Requirements::VerdictKind",
                "referentType": "Enumeration",
                "originalID": "_11_5EAPbeta_be00301_1147937844838_242658_2617"
            }
        }
    elif type in predefined_types:
        return {
            "href": f"http://www.omg.org/spec/SysML/20181001/SysML.xmi#SysML_dataType.{type}",
            "referenceExtension_attributes": {
                "referentPath": f"SysML::Libraries::PrimitiveValueTypes::{type}",
                "referentType": "DataType",
                "originalID": get_oringinal_id(type)
            }
        }
    
def get_oringinal_id(type):
    original_ids = {
        "String": "_16_5_1_12c903cb_1245415335546_479030_4092",
        "Real": "_11_5EAPbeta_be00301_1147431819399_50461_1671",
        "Number": "_16_5_1_12c903cb_1245415335546_535327_4089",
        "Complex": "_11_5EAPbeta_be00301_1147431846238_895928_1691",
        "Integer": "_16_5_1_12c903cb_1245415335546_8641_4088",
        "Boolean": "_16_5_1_12c903cb_1245415335546_39033_4086"
    }
    return original_ids.get(type, original_ids["String"])

si_definitions = {
  "pressure": "_16_5_1_ff3038a_1245649125606_277898_7819",
  "cubicMetre^-1": "_16_5_1_ff3038a_1245576449123_60912_5529",
  "luminousIntensity^1": "_16_5_1_ff3038a_1245627152967_888418_4090",
  "luminance": "_16_5_1_ff3038a_1245622386711_471754_5572",
  "electricCharge": "_16_5_2_ff3038a_1245876548714_134472_6479",
  "henry": "_16_5_2_ff3038a_1245907250646_743066_6566",
  "kilogram^-1": "_16_5_1_ff3038a_1245576473997_364008_5541",
  "specificVolume": "_16_5_1_ff3038a_1245577314375_791820_5705",
  "mole^1": "_16_5_1_ff3038a_1245621788043_555820_5228",
  "cubicMetre": "_16_5_1_ff3038a_1245574101728_24418_5022",
  "velocity": "_16_5_1_12c903cb_1245421408843_321338_6105",
  "catalyticActivity": "_16_5_2_ff3038a_1245916961919_68756_7635",
  "siemens": "_16_5_2_ff3038a_1245881602473_580919_8246",
  "squareMetre^-1": "_16_5_1_ff3038a_1245620463314_379886_4896",
  "second^-2": "_16_5_1_ff3038a_1245572071165_445017_4513",
  "frequency": "_16_5_1_ff3038a_1245635934912_736290_6808",
  "metre": "_16_5_1_12c903cb_1245421859000_233075_6259",
  "steradian^1": "_16_5_2_ff3038a_1245911773027_797590_10119",
  "amountOfSubstance^1": "_16_5_1_ff3038a_1245621989379_154077_5297",
  "electricResistance": "_16_5_2_ff3038a_1245904955822_831526_6203",
  "area": "_16_5_1_ff3038a_1245574704422_315574_5123",
  "thermodynamic  temperature": "_16_5_1_ff3038a_1245561946382_220901_4922",
  "second^1": "_16_5_2_ff3038a_1245876626183_588540_6501",
  "gray": "_16_5_2_ff3038a_1245913960399_139072_7071",
  "length^-1": "_16_5_1_ff3038a_1245619938866_138770_4530",
  "amountOfSubstanceConcentration": "_16_5_1_ff3038a_1245622041717_945809_5322",
  "electricPotentialDifference": "_16_5_2_ff3038a_1245879016598_72888_7060",
  "massDensity": "_16_5_1_ff3038a_1245577283988_935989_5693",
  "cubicMetrePerKilogram": "_16_5_1_ff3038a_1245576376484_222081_5505",
  "magneticFlux^1": "_16_5_2_ff3038a_1245906752222_486756_6143",
  "farad": "_16_5_2_ff3038a_1245880193909_251321_7619",
  "length^1": "_16_5_1_12c903cb_1245421215656_727759_6063",
  "energy": "_16_5_1_ff3038a_1245651380551_175464_8207",
  "magneticFluxDensity": "_16_5_2_ff3038a_1245907014797_925547_6254",
  "luminousIntensity": "_16_5_1_ff3038a_1245562367854_934507_4975",
  "sievert": "_16_5_2_ff3038a_1245915277433_125892_7344",
  "time": "_16_5_1_12c903cb_1245421159796_463381_6045",
  "electricCurrent": "_16_5_1_ff3038a_1245561719620_187312_4893",
  "coulomb": "_16_5_2_ff3038a_1245876355489_965842_6415",
  "newton^1": "_16_5_1_ff3038a_1245648828671_127179_7689",
  "lumen^1": "_16_5_2_ff3038a_1245912614964_359407_10731",
  "squareMetre^1": "_16_5_1_ff3038a_1245631630937_794364_6381",
  "electricPotentialDifference^1": "_16_5_2_ff3038a_1245879411297_505602_7271",
  "metre^3": "_16_5_1_ff3038a_1245574363652_637927_5075",
  "metrePerSecond": "_16_5_1_ff3038a_1245566079651_244134_4218",
  "reciprocalMetre": "_16_5_1_ff3038a_1245619674532_995912_4455",
  "kilogramPerCubicMetre": "_16_5_1_ff3038a_1245576305098_969824_5493",
  "radionuclideActivity": "_16_5_2_ff3038a_1245913337045_775596_5568",
  "joule": "_16_5_1_ff3038a_1245651129379_396773_8177",
  "mass": "_16_5_1_ff3038a_1245560498149_315686_4721",
  "kilogram": "_16_5_1_ff3038a_1245558746041_85423_4497",
  "candela^1": "_16_5_1_ff3038a_1245624879184_448030_5600",
  "electricCurrent^1": "_16_5_1_ff3038a_1245620755885_473756_5000",
  "steradian": "_16_5_1_ff3038a_1245631690713_635911_6406",
  "lux": "_16_5_2_ff3038a_1245912660639_636012_10756",
  "volt": "_16_5_2_ff3038a_1245879251502_778810_7155",
  "ampere^-1": "_16_5_2_ff3038a_1245879082508_499699_7090",
  "power^1": "_16_5_2_ff3038a_1245877539695_991396_6953",
  "waveNumber": "_16_8beta_2104050f_1262941875423_288381_6015",
  "candela": "_16_5_1_ff3038a_1245558862128_467276_4557",
  "solidAngle^1": "_16_5_2_ff3038a_1245911939977_578485_10183",
  "second": "_16_5_1_ff3038a_1245558801890_74944_4509",
  "volt^-1": "_16_5_2_ff3038a_1245879834405_760194_7515",
  "metre^1": "_16_5_1_ff3038a_1245566164364_181533_4262",
  "becquerel": "_16_5_2_ff3038a_1245913235108_646371_5543",
  "mass^-1": "_16_5_1_ff3038a_1245577453361_860930_5741",
  "electricCharge^1": "_16_5_2_ff3038a_1245879856445_475822_7527",
  "mole": "_16_5_1_ff3038a_1245558843953_788987_4545",
  "ohm": "_16_5_2_ff3038a_1245905095808_65656_6261",
  "absorbedDose": "_16_5_2_ff3038a_1245914701940_121613_7107",
  "ampere^1": "_16_5_1_ff3038a_1245620375639_687286_4844",
  "luminousFlux": "_16_5_2_ff3038a_1245912007076_777515_10208",
  "amperePerMetre": "_16_5_1_ff3038a_1245620345101_24980_4832",
  "force": "_16_5_1_ff3038a_1245648213998_639958_7320",
  "coulomb^1": "_16_5_2_ff3038a_1245879806287_917755_7503",
  "mass^1": "_16_5_1_ff3038a_1245577346250_736327_5717",
  "volt^1": "_16_5_2_ff3038a_1245905027771_77460_6233",
  "acceleration": "_16_5_1_ff3038a_1245572732537_166833_4656",
  "ampere": "_16_5_1_ff3038a_1245558816590_642897_4521",
  "molePerCubicMetre": "_16_5_1_ff3038a_1245621843706_548123_5253",
  "volume^-1": "_16_5_1_ff3038a_1245577431737_847150_5729",
  "radian": "_16_5_1_ff3038a_1245630854252_4923_4927",
  "kilogram^1": "_16_5_1_ff3038a_1245576416259_716807_5517",
  "time^-2": "_16_5_1_ff3038a_1245572244854_270219_4599",
  "area^1": "_16_5_1_ff3038a_1245631872299_270078_6488",
  "area^-1": "_16_5_1_ff3038a_1245620804223_419041_5025",
  "power": "_16_5_1_ff3038a_1245653173406_317868_6070",
  "inductance": "_16_5_2_ff3038a_1245907353183_604769_6610",
  "length": "_16_5_1_12c903cb_1245421062500_889852_6027",
  "watt^1": "_16_5_2_ff3038a_1245879205511_212358_7130",
  "hertz": "_16_5_1_ff3038a_1245635839350_566315_6772",
  "weber": "_16_5_2_ff3038a_1245905540968_877283_6682",
  "cubicMetre^1": "_16_5_1_ff3038a_1245576507909_20215_5565",
  "magneticFieldStrength": "_16_5_1_ff3038a_1245620876973_617416_5050",
  "capacitance": "_16_5_2_ff3038a_1245880281866_255364_7655",
  "candelaPerSquareMetre": "_16_5_1_ff3038a_1245622365666_778133_5560",
  "amountOfSubstance": "_16_5_1_ff3038a_1245562275118_72899_4951",
  "electricCurrent^-1": "_16_5_2_ff3038a_1245878932369_145446_7035",
  "time^-1": "_16_5_1_12c903cb_1245421328703_345329_6084",
  "watt": "_16_5_1_ff3038a_1245653032256_787950_6009",
  "solidAngle": "_16_5_1_ff3038a_1245631823212_993011_6476",
  "tesla": "_16_5_2_ff3038a_1245906945398_58518_6216",
  "squareMetre": "_16_5_1_ff3038a_1245574035803_816953_5010",
  "thermodynamicTemperature^1": "_16_5_2_ff3038a_1245911202884_717759_9835",
  "degreeCelsius": "_16_5_2_ff3038a_1245910546708_321035_9774",
  "illuminance": "_16_5_2_ff3038a_1245912778038_470552_10792",
  "electricPotentialDifference^-1": "_16_5_2_ff3038a_1245879886452_849671_7539",
  "metrePerSecondSquared": "_16_5_1_ff3038a_1245571990117_239543_4489",
  "amperePerSquareMetre": "_16_5_1_ff3038a_1245620309464_598579_4820",
  "ISQ": "_16_5_1_12c903cb_1245420666875_649178_5972",
  "second^-1": "_16_5_1_ff3038a_1245566190500_100408_4274",
  "kelvin": "_16_5_1_ff3038a_1245558834605_618778_4533",
  "joule^1": "_16_5_1_ff3038a_1245652981607_473793_5984",
  "katal": "_16_5_2_ff3038a_1245916884571_139193_7599",
  "volume^1": "_16_5_1_ff3038a_1245577467499_731134_5753",
  "currentDensity": "_16_5_1_ff3038a_1245621150259_658061_5095",
  "length^2": "_16_5_1_ff3038a_1245574758460_939764_5147",
  "weber^1": "_16_5_2_ff3038a_1245906708835_411690_6118",
  "energy^1": "_16_5_1_ff3038a_1245653130830_116947_6045",
  "celsiusTemperature": "_16_5_2_ff3038a_1245910676883_58178_9811",
  "lumen": "_16_5_2_ff3038a_1245911832553_560650_10144",
  "electricConductance": "_16_5_2_ff3038a_1245881759775_329691_8290",
  "magneticFlux": "_16_5_2_ff3038a_1245905611730_950832_6718",
  "pascal": "_16_5_1_ff3038a_1245649035695_379354_7789",
  "volume": "_16_5_1_ff3038a_1245574723397_963139_5135",
  "metre^2": "_16_5_1_ff3038a_1245574215640_368061_5040",
  "length^3": "_16_5_1_ff3038a_1245574786533_25260_5159",
  "metre^-1": "_16_5_1_ff3038a_1245619727091_145672_4467",
  "SI": "_16_5_1_12c903cb_1245421785562_341925_6241",
  "time^1": "_16_5_2_ff3038a_1245876672637_54433_6531",
  "doseEquivalent": "_16_5_2_ff3038a_1245915652619_433793_7380",
  "luminousFlux^1": "_16_5_2_ff3038a_1245912569676_256493_10706",
  "planeAngle": "_16_5_1_ff3038a_1245631114039_195948_5941",
  "force^1": "_16_5_1_ff3038a_1245648876958_56341_7713",
  "newton": "_16_5_1_ff3038a_1245648094949_479814_7276",
  "amountOfElectricityQK": "_16_5_2_ff3038a_1245877260809_940768_6730",
  "electricCharge^1QKF": "_16_5_2_ff3038a_1245877235730_247990_6718",
  "radianFluxQK": "_16_5_2_ff3038a_1245877523896_580344_6941",
  "speedQK": "_16_5_2_ff3038a_1245787622995_80217_23688",
  "velocity^1QKF": "_16_5_2_ff3038a_1245787656657_825973_23700",
  "electromotiveForce": "_16_5_2_ff3038a_1245879463366_706263_7296"
}