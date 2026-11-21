/**
 * Comprehensive Official Dataset of Indian States & UTs (28 States + 8 Union Territories)
 * Includes all official 750+ districts, municipal corporations, tier-1/tier-2/tier-3 cities.
 */
(function(window) {
    const INDIA_STATES_AND_CITIES = {
        "Andhra Pradesh": [
            "Anakapalli", "Ananthapuramu", "Annamayya", "Bapatla", "Chittoor", "Dr. B.R. Ambedkar Konaseema",
            "East Godavari", "Eluru", "Guntur", "Kakinada", "Kurnool", "Nandyal", "NTR (Vijayawada)",
            "Palnadu", "Parvathipuram Manyam", "Prakasam (Ongole)", "Srikakulam", "Sri Potti Sriramulu Nellore",
            "Sri Sathya Sai", "Tirupati", "Visakhapatnam", "Vizianagaram", "West Godavari (Bhimavaram)", "YSR Kadapa",
            "Rajahmundry", "Tenali", "Hindupur", "Machilipatnam", "Tuni", "Adoni", "Dharmavaram", "Guntakal", "Proddatur"
        ],
        "Arunachal Pradesh": [
            "Anjaw", "Changlang", "Dibang Valley", "East Kameng", "East Siang (Pasighat)", "Kamle", "Kra Daadi",
            "Kurung Kumey", "Lepa Rada", "Lohit (Tezu)", "Longding", "Lower Dibang Valley (Roing)", "Lower Subansiri (Ziro)",
            "Namsai", "Pakke Kessang", "Papum Pare (Itanagar)", "Shi Yomi", "Siang", "Tawang", "Tirap (Khonsa)",
            "Upper Siang", "Upper Subansiri", "West Kameng (Bomdila)", "West Siang (Along)", "Naharlagun"
        ],
        "Assam": [
            "Bajali", "Baksa", "Barpeta", "Biswanath", "Bongaigaon", "Cachar (Silchar)", "Charaideo", "Chirang",
            "Darrang (Mangaldoi)", "Dhemaji", "Dhubri", "Dibrugarh", "Dima Hasao (Haflong)", "Goalpara", "Golaghat",
            "Hailakandi", "Hojai", "Jorhat", "Kamrup (Amingaon)", "Kamrup Metropolitan (Guwahati)", "Karbi Anglong (Diphu)",
            "Karimganj", "Kokrajhar", "Lakhimpur (North Lakhimpur)", "Majuli", "Morigaon", "Nagaon", "Nalbari",
            "Sivasagar", "Sonitpur (Tezpur)", "South Salmara-Mankachar", "Tinsukia", "Udalguri", "West Karbi Anglong", "Lumding"
        ],
        "Bihar": [
            "Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur", "Bhojpur (Arrah)", "Buxar", "Darbhanga",
            "East Champaran (Motihari)", "Gaya", "Gopalganj", "Jamui", "Jehanabad", "Kaimur (Bhabua)", "Katihar",
            "Khagaria", "Kishanganj", "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur", "Nalanda (Bihar Sharif)",
            "Nawada", "Patna", "Purnia", "Rohtas (Sasaram)", "Saharsa", "Samastipur", "Saran (Chhapra)", "Sheikhpura",
            "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali (Hajipur)", "West Champaran (Bettiah)", "Danapur", "Dehri", "Jamalpur"
        ],
        "Chhattisgarh": [
            "Balod", "Baloda Bazar", "Balrampur", "Bastar (Jagdalpur)", "Bemetara", "Bijapur", "Bilaspur", "Dantewada",
            "Dhamtari", "Durg", "Gariaband", "Gaurela-Pendra-Marwahi", "Janjgir-Champa", "Jashpur", "Kabirdham (Kawardha)",
            "Kanker", "Kondagaon", "Korba", "Koriya", "Mahasamund", "Manendragarh-Chirmiri-Bharatpur", "Mohla-Manpur-Ambagarh Chowki",
            "Mungeli", "Narayanpur", "Raigarh", "Raipur", "Rajnandgaon", "Sarangarh-Bilaigarh", "Sakti", "Sukma", "Surajpur", "Surguja (Ambikapur)", "Bhilai", "Bhatapara"
        ],
        "Goa": [
            "North Goa (Panaji)", "South Goa (Margao)", "Vasco da Gama", "Mapusa", "Ponda", "Bicholim", "Curchorem", "Cuncolim", "Valpoi", "Pernem", "Quepem", "Sanguem", "Canacona"
        ],
        "Gujarat": [
            "Ahmedabad", "Amreli", "Anand", "Aravalli (Modasa)", "Banaskantha (Palanpur)", "Bharuch", "Bhavnagar", "Botad",
            "Chhota Udaipur", "Dahod", "Dang (Ahwa)", "Devbhumi Dwarka", "Gandhinagar", "Gir Somnath (Veraval)", "Jamnagar",
            "Junagadh", "Kheda (Nadiad)", "Kutch (Bhuj)", "Mahisagar (Lunawada)", "Mehsana", "Morbi", "Narmada (Rajpipla)",
            "Navsari", "Panchmahal (Godhra)", "Patan", "Porbandar", "Rajkot", "Sabarkantha (Himmatnagar)", "Surat",
            "Surendranagar", "Tapi (Vyara)", "Vadodara", "Valsad", "Vapi", "Gondal", "Deesa", "Jetpur", "Anjar", "Bhadreswar"
        ],
        "Haryana": [
            "Ambala", "Bhiwani", "Charkhi Dadri", "Faridabad", "Fatehabad", "Gurugram", "Hisar", "Jhajjar", "Jind",
            "Kaithal", "Karnal", "Kurukshetra (Thanesar)", "Mahendragarh (Narnaul)", "Nuh", "Palwal", "Panchkula",
            "Panipat", "Rewari", "Rohtak", "Sirsa", "Sonipat", "Yamunanagar", "Bahadurgarh", "Hansi", "Tohana", "Gharaunda"
        ],
        "Himachal Pradesh": [
            "Bilaspur", "Chamba", "Hamirpur", "Kangra (Dharamshala)", "Kinnaur (Reckong Peo)", "Kullu", "Lahaul and Spiti (Keylong)",
            "Mandi", "Shimla", "Sirmaur (Nahan)", "Solan", "Una", "Manali", "Baddi", "Palampur", "Paonta Sahib", "Sundernagar", "Dalhousie"
        ],
        "Jharkhand": [
            "Bokaro (Bokaro Steel City)", "Chatra", "Deoghar", "Dhanbad", "Dumka", "East Singhbhum (Jamshedpur)", "Garhwa",
            "Giridih", "Godda", "Gumla", "Hazaribagh", "Jamtara", "Khunti", "Koderma (Jhumri Telaiya)", "Latehar",
            "Lohardaga", "Pakur", "Palamu (Daltonganj)", "Ramgarh", "Ranchi", "Sahibganj", "Seraikela Kharsawan", "Simdega", "West Singhbhum (Chaibasa)", "Chirkunda", "Phusro"
        ],
        "Karnataka": [
            "Bagalkote", "Ballari (Bellary)", "Belagavi (Belgaum)", "Bengaluru Urban", "Bengaluru Rural", "Bidar",
            "Chamarajanagara", "Chikkaballapura", "Chikkamagaluru", "Chitradurga", "Dakshina Kannada (Mangaluru)",
            "Davanagere", "Dharwad (Hubballi-Dharwad)", "Gadag", "Hassan", "Haveri", "Kalaburagi (Gulbarga)", "Kodagu (Madikeri)",
            "Kolar", "Koppal", "Mandya", "Mysuru (Mysore)", "Raichur", "Ramanagara", "Shivamogga (Shimoga)", "Tumakuru (Tumkur)",
            "Udupi", "Uttara Kannada (Karwar)", "Vijayanagara (Hosapete)", "Vijayapura (Bijapur)", "Yadgir", "Bhadravati"
        ],
        "Kerala": [
            "Alappuzha", "Ernakulam (Kochi)", "Idukki (Painavu)", "Kannur", "Kasaragod", "Kollam", "Kottayam",
            "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad (Kalpetta)",
            "Thalassery", "Ponnani", "Vatakara", "Kanhangad", "Payyanur", "Koyilandy", "Neyyattinkara", "Kayamkulam"
        ],
        "Madhya Pradesh": [
            "Agar Malwa", "Alirajpur", "Anuppur", "Ashoknagar", "Balaghat", "Barwani", "Betul", "Bhind", "Bhopal",
            "Burhanpur", "Chhatarpur", "Chhindwara", "Damoh", "Datia", "Dewas", "Dhar", "Dindori", "Guna", "Gwalior",
            "Harda", "Hoshangabad (Narmadapuram)", "Indore", "Jabalpur", "Jhabua", "Katni", "Khandwa (East Nimar)",
            "Khargone (West Nimar)", "Mandla", "Mandsaur", "Morena", "Narsinghpur", "Neemuch", "Niwari", "Panna", "Raisen",
            "Rajgarh", "Ratlam", "Rewa", "Sagar", "Satna", "Sehore", "Seoni", "Shahdol", "Shajapur", "Sheopur", "Shivpuri",
            "Sidhi", "Singrauli", "Takamgarh", "Ujjain", "Umaria", "Vidisha", "Itarsi", "Nagda", "Pithampur"
        ],
        "Maharashtra": [
            "Ahmednagar (Ahilyanagar)", "Akola", "Amravati", "Chhatrapati Sambhajinagar (Aurangabad)", "Beed", "Bhandara",
            "Buldhana", "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna", "Kolhapur", "Latur",
            "Mumbai City", "Mumbai Suburban", "Nagpur", "Nanded", "Nandurbar", "Nashik", "Navi Mumbai", "Dharashiv (Osmanabad)",
            "Palghar", "Parbhani", "Pune", "Raigad (Alibag)", "Ratnagiri", "Sangli", "Satara", "Sindhudurg", "Solapur",
            "Thane", "Wardha", "Washim", "Yavatmal", "Kalyan-Dombivli", "Vasai-Virar", "Mira-Bhayandar", "Bhiwandi", "Ulhasnagar", "Panvel", "Ichalkaranji", "Malegaon", "Bhusawal"
        ],
        "Manipur": [
            "Bishnupur", "Chandel", "Churachandpur", "Imphal East", "Imphal West", "Jiribam", "Kakching", "Kamjong",
            "Kangpokpi", "Noney", "Pherzawl", "Senapati", "Tamenglong", "Tengnoupal", "Thoubal", "Ukhrul"
        ],
        "Meghalaya": [
            "East Garo Hills (Williamnagar)", "East Jaintia Hills (Khliehriat)", "East Khasi Hills (Shillong)", "Eastern West Khasi Hills (Mairang)",
            "North Garo Hills (Resubelpara)", "Ri Bhoi (Nongpoh)", "South Garo Hills (Baghmara)", "South West Garo Hills (Ampati)",
            "South West Khasi Hills (Mawkyrwat)", "West Garo Hills (Tura)", "West Jaintia Hills (Jowai)", "West Khasi Hills (Nongstoin)"
        ],
        "Mizoram": [
            "Aizawl", "Champhai", "Hnahthial", "Khawzawl", "Kolasib", "Lawngtlai", "Lunglei", "Mamit", "Saiha", "Serchhip", "Saitual"
        ],
        "Nagaland": [
            "Chümoukedima", "Dimapur", "Kiphire", "Kohima", "Longleng", "Mokokchung", "Mon", "Niuland", "Noklak", "Peren", "Phek", "Shamator", "Tseminyu", "Tuensang", "Wokha", "Zunheboto"
        ],
        "Odisha": [
            "Angul", "Balangir", "Balasore (Baleswar)", "Bargarh", "Bhadrak", "Baudh (Boudh)", "Cuttack", "Deogarh (Debagarh)",
            "Dhenkanal", "Gajapati", "Ganjam (Berhampur)", "Jagatsinghpur", "Jajpur", "Jharsuguda", "Kalahandi (Bhawanipatna)",
            "Kandhamal (Phulbani)", "Kendrapara", "Kendujhar (Keonjhar)", "Khordha (Bhubaneswar)", "Koraput (Jeypore)",
            "Malkangiri", "Mayurbhanj (Baripada)", "Nabarangpur", "Nayagarh", "Nuapada", "Puri", "Rayagada", "Sambalpur",
            "Subarnapur (Sonepur)", "Sundargarh (Rourkela)"
        ],
        "Punjab": [
            "Amritsar", "Barnala", "Bathinda", "Faridkot", "Fatehgarh Sahib", "Fazilka", "Firozpur", "Gurdaspur", "Hoshiarpur",
            "Jalandhar", "Kapurthala", "Ludhiana", "Malerkotla", "Mansa", "Moga", "Pathankot", "Patiala", "Rupnagar (Ropar)",
            "Sahibzada Ajit Singh Nagar (Mohali)", "Sangrur", "Shahid Bhagat Singh Nagar (Nawanshahr)", "Sri Muktsar Sahib", "Tarn Taran", "Abohar", "Batala", "Khanna", "Phagwara", "Rajpura"
        ],
        "Rajasthan": [
            "Ajmer", "Alwar", "Anupgarh", "Balotra", "Banswara", "Baran", "Barmer", "Beawar", "Bharatpur", "Bhilwara", "Bikaner",
            "Bundi", "Chittorgarh", "Churu", "Dausa", "Deeg", "Didwana-Kuchaman", "Dholpur", "Dudu", "Dungarpur", "Gangapur City",
            "Hanumangarh", "Jaipur Urban", "Jaipur Rural", "Jaisalmer", "Jalore", "Jhalawar", "Jhunjhunu", "Jodhpur Urban",
            "Jodhpur Rural", "Karauli", "Kekri", "Kota", "Kotputli-Behror", "Khairthal-Tijara", "Nagaur", "Neem Ka Thana",
            "Pali", "Phalodi", "Pratapgarh", "Rajsamand", "Salumbar", "Sanchore", "Sawai Madhopur", "Shahpura", "Sikar", "Sirohi",
            "Sri Ganganagar", "Tonk", "Udaipur", "Bhiwadi", "Kishangarh", "Sujangarh", "Hindaun", "Nimbahera", "Makrana"
        ],
        "Sikkim": [
            "Gangtok (East Sikkim)", "Mangan (North Sikkim)", "Namchi (South Sikkim)", "Gyalshing (West Sikkim)", "Pakyong", "Soreng", "Singtam", "Rangpo", "Jorethang", "Ravangla"
        ],
        "Tamil Nadu": [
            "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri", "Dindigul", "Erode", "Kanchipuram",
            "Kanyakumari (Nagercoil)", "Karur", "Krishnagiri (Hosur)", "Madurai", "Mayiladuthurai", "Nagapattinam", "Namakkal",
            "Nilgiris (Udhagamandalam / Ooty)", "Perambalur", "Pudukkottai", "Ramanathapuram", "Ranipet", "Salem", "Sivaganga (Karaikudi)",
            "Tenkasi", "Thanjavur", "Theni", "Thoothukudi (Tuticorin)", "Tiruchirappalli (Trichy)", "Tirunelveli", "Tirupathur",
            "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Tiruvarur", "Vellore", "Viluppuram", "Virudhunagar (Sivakasi)", "Ambur", "Neyveli", "Pollachi", "Kumbakonam", "Gudiyatham"
        ],
        "Telangana": [
            "Adilabad", "Bhadradri Kothagudem", "Hanamkonda (Warangal)", "Hyderabad", "Jagtial", "Jangaon", "Jayashankar Bhupalpally",
            "Jogulamba Gadwal", "Kamareddy", "Karimnagar", "Khammam", "Kumuram Bheem Asifabad", "Mahabubabad", "Mahbubnagar",
            "Mancherial", "Medak", "Medchal-Malkajgiri", "Mulugu", "Nagarkurnool", "Nalgonda", "Narayanpet", "Nirmal", "Nizamabad",
            "Peddapalli (Ramagundam)", "Rajanna Sircilla", "Ranga Reddy", "Sangareddy", "Siddipet", "Suryapet", "Vikarabad", "Wanaparthy", "Warangal", "Yadadri Bhuvanagiri", "Miryalaguda", "Bodhan"
        ],
        "Tripura": [
            "Dhalai (Ambassa)", "Gomati (Udaipur)", "Khowai", "North Tripura (Dharmanagar)", "Sepahijala (Bishramganj)", "South Tripura (Belonia)", "Unakoti (Kailashahar)", "West Tripura (Agartala)", "Teliamura", "Sabroom"
        ],
        "Uttar Pradesh": [
            "Agra", "Aligarh", "Ambedkar Nagar (Akbarpur)", "Amethi", "Amroha (Jyotiba Phule Nagar)", "Auraiya", "Ayodhya (Faizabad)",
            "Azamgarh", "Baghpat", "Bahraich", "Ballia", "Balrampur", "Banda", "Barabanki", "Bareilly", "Basti", "Bhadohi (Sant Ravidas Nagar)",
            "Bijnor", "Budaun", "Bulandshahr", "Chandauli", "Chitrakoot", "Deoria", "Etah", "Etawah", "Farrukhabad", "Fatehpur",
            "Firozabad", "Gautam Buddha Nagar (Noida / Greater Noida)", "Ghaziabad", "Ghazipur", "Gonda", "Gorakhpur", "Hamirpur",
            "Hapur (Panchsheel Nagar)", "Hardoi", "Hathras (Mahamaya Nagar)", "Jalaun (Orai)", "Jaunpur", "Jhansi", "Kannauj",
            "Kanpur Dehat", "Kanpur Nagar", "Kasganj (Kanshiram Nagar)", "Kaushambi", "Kushinagar (Padrauna)", "Lakhimpur Kheri",
            "Lalitpur", "Lucknow", "Maharajganj", "Mahoba", "Mainpuri", "Mathura", "Mau", "Meerut", "Mirzapur", "Moradabad",
            "Muzaffarnagar", "Pilibhit", "Pratapgarh", "Prayagraj (Allahabad)", "Raebareli", "Rampur", "Saharanpur", "Sambhal (Bhimnagar)",
            "Sant Kabir Nagar (Khalilabad)", "Shahjahanpur", "Shamli", "Shravasti", "Siddharthnagar", "Sitapur", "Sonbhadra (Robertsganj)",
            "Sultanpur", "Unnao", "Varanasi", "Chandausi", "Modinagar", "Khurja", "Shikohabad", "Tanda"
        ],
        "Uttarakhand": [
            "Almora", "Bageshwar", "Chamoli (Gopeshwar)", "Champawat", "Dehradun", "Haridwar", "Nainital", "Pauri Garhwal",
            "Pithoragarh", "Rudraprayag", "Tehri Garhwal", "Udham Singh Nagar (Rudrapur / Haldwani)", "Uttarkashi", "Roorkee", "Kashipur", "Rishikesh", "Ramnagar", "Kotdwar", "Mussoorie"
        ],
        "West Bengal": [
            "Alipurduar", "Bankura", "Birbhum (Suri / Bolpur)", "Cooch Behar", "Dakshin Dinajpur (Balurghat)", "Darjeeling",
            "Hooghly (Chinsurah / Dankuni)", "Howrah", "Jalpaiguri", "Jhargram", "Kalimpong", "Kolkata", "Malda",
            "Murshidabad (Baharampur / Jangipur)", "Nadia (Krishnanagar / Ranaghat)", "North 24 Parganas (Barasat / Barrackpore)",
            "Paschim Bardhaman (Asansol / Durgapur)", "Paschim Medinipur (Kharagpur)", "Purba Bardhaman", "Purba Medinipur (Haldia)",
            "Purulia", "South 24 Parganas (Baruipur)", "Uttar Dinajpur (Raiganj)", "Siliguri", "Shantipur", "Basirhat", "Chakdaha"
        ],
        "Delhi (UT)": [
            "Central Delhi", "East Delhi", "New Delhi", "North Delhi", "North East Delhi", "North West Delhi", "Shahdara",
            "South Delhi", "South East Delhi", "South West Delhi", "West Delhi", "Dwarka", "Rohini", "Connaught Place", "Karol Bagh", "Lajpat Nagar", "Saket", "Vasant Kunj"
        ],
        "Chandigarh (UT)": [
            "Chandigarh"
        ],
        "Jammu and Kashmir (UT)": [
            "Anantnag", "Bandipora", "Baramulla", "Budgam", "Doda", "Ganderbal", "Jammu", "Kathua", "Kishtwar", "Kulgam",
            "Kupwara", "Poonch", "Pulwama", "Rajouri", "Ramban", "Reasi", "Samba", "Shopian", "Sopore", "Srinagar", "Udhampur"
        ],
        "Ladakh (UT)": [
            "Leh", "Kargil", "Diskit", "Padum", "Nubra"
        ],
        "Puducherry (UT)": [
            "Puducherry", "Karaikal", "Mahe", "Yanam", "Ozhukarai"
        ],
        "Andaman and Nicobar Islands (UT)": [
            "Nicobar (Car Nicobar)", "North and Middle Andaman (Mayabunder)", "South Andaman (Port Blair)", "Diglipur", "Rangat"
        ],
        "Dadra and Nagar Haveli and Daman and Diu (UT)": [
            "Daman", "Diu", "Dadra and Nagar Haveli (Silvassa)", "Amli", "Naroli"
        ],
        "Lakshadweep (UT)": [
            "Kavaratti", "Agatti", "Andrott", "Minicoy", "Amini", "Kadmat"
        ]
    };

    /**
     * Initializes and synchronizes State and City Dropdowns with auto-selection support.
     * @param {string} stateSelectId - ID of the state <select> element
     * @param {string} citySelectId - ID of the city <select> element
     * @param {string} defaultState - Initially selected state
     * @param {string} defaultCity - Initially selected city
     */
    function initIndianStateCityDropdowns(stateSelectId, citySelectId, defaultState, defaultCity) {
        const stateSelect = document.getElementById(stateSelectId);
        const citySelect = document.getElementById(citySelectId);

        if (!stateSelect || !citySelect) return;

        // 1. Populate State Dropdown
        let stateHtml = '<option value="">-- Select State --</option>';
        const stateKeys = Object.keys(INDIA_STATES_AND_CITIES).sort();
        let stateFound = false;
        const cleanDefaultState = (defaultState || '').trim().toLowerCase();

        stateKeys.forEach(state => {
            const isMatch = cleanDefaultState && (state.toLowerCase() === cleanDefaultState || cleanDefaultState.includes(state.toLowerCase()) || state.toLowerCase().includes(cleanDefaultState));
            if (isMatch) stateFound = true;
            stateHtml += `<option value="${state}" ${isMatch ? 'selected' : ''}>${state}</option>`;
        });

        if (defaultState && !stateFound) {
            stateHtml += `<option value="${defaultState}" selected>${defaultState}</option>`;
        }

        stateSelect.innerHTML = stateHtml;

        // Helper function to update cities for selected state
        function updateCities(selectedStateName, targetCity) {
            if (!citySelect) return;
            if (!selectedStateName) {
                citySelect.innerHTML = '<option value="">-- Select City --</option>';
                return;
            }

            // Find matching state in dictionary
            let matchedStateKey = Object.keys(INDIA_STATES_AND_CITIES).find(k => k.toLowerCase() === selectedStateName.trim().toLowerCase());
            let cities = matchedStateKey ? INDIA_STATES_AND_CITIES[matchedStateKey] : [];

            let cityHtml = '<option value="">-- Select City --</option>';
            let cityFound = false;
            const cleanTargetCity = (targetCity || '').trim().toLowerCase();

            if (cities && cities.length > 0) {
                cities.forEach(city => {
                    const isCityMatch = cleanTargetCity && (city.toLowerCase() === cleanTargetCity || cleanTargetCity === city.toLowerCase().replace(/[^a-z0-9]/g, ''));
                    if (isCityMatch) cityFound = true;
                    cityHtml += `<option value="${city}" ${isCityMatch ? 'selected' : ''}>${city}</option>`;
                });
            }

            if (targetCity && !cityFound) {
                cityHtml += `<option value="${targetCity}" selected>${targetCity}</option>`;
            }

            cityHtml += '<option value="Other">Other (City not listed)</option>';
            citySelect.innerHTML = cityHtml;
        }

        // 2. Populate initial City Dropdown
        const activeState = stateSelect.value || defaultState;
        updateCities(activeState, defaultCity);

        // 3. Event Listener on State Change
        stateSelect.addEventListener('change', function() {
            updateCities(this.value, '');
        });
    }

    // Export to global window
    window.INDIA_STATES_AND_CITIES = INDIA_STATES_AND_CITIES;
    window.initIndianStateCityDropdowns = initIndianStateCityDropdowns;

})(window);
