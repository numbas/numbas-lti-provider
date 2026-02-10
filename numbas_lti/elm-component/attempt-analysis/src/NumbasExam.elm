module NumbasExam exposing 
  ( Exam
  , QuestionPath
  , QuestionSubset
  , Question
  , Part
  , PartInfo
  , NumbasExamError(..)
  , errorToString
  , rewrite_part_path
  , decode
  , fromString
  , get_question
  , get_part
  , all_parts
  , prev_part
  , next_part
  , part_type_names
  , short_part_label
  , part_label
  )

import Dict
import GroupPartPath exposing (GroupPartPath)
import Json.Decode as JD
import Json.Decode.Extra as JDE
import List.Extra as LE
import PartPath exposing (PartPath)
import Tuple exposing (pair, first, second)
import Util exposing (alpha)

fi = String.fromInt

jam = JDE.andMap

type alias QuestionPath = (Int, Int)

type alias Exam =
  { name : String
  , question_groups : List (List Question)
  , source : JD.Value
  }

type alias Question =
  { name : String
  , parts : List Part
  , source : JD.Value
  }

type alias PartInfo =
  { type_ : String
  , source : JD.Value
  }

type alias Part = 
  { info : PartInfo
  , gaps : List PartInfo
  , steps : List PartInfo
  }

type alias QuestionSubset = List (List Int)

-- Rewrite a part path from attempt data to the path in the exam's definition order, including the group
rewrite_part_path : QuestionSubset -> Exam -> PartPath -> GroupPartPath
rewrite_part_path question_subset exam (qn,pn,mgn) =
  let
    qs : List (Int, Int)
    qs = 
      question_subset
      |> List.indexedMap (\gn -> List.map (pair gn))
      |> List.concatMap identity

    (ngn,nqn) = LE.getAt qn qs |> Maybe.withDefault (-1,-1)
  in
    (ngn, (nqn, pn, mgn))

type NumbasExamError
  = FormatError String
  | JsonError JD.Error

errorToString : NumbasExamError -> String
errorToString error = case error of
  FormatError format_error -> format_error
  JsonError json_error -> "JSON decoding error: "++(JD.errorToString json_error)

all_parts : Exam -> List (GroupPartPath, PartInfo)
all_parts exam =
  let
    groups : List (List Question)
    groups = exam.question_groups

    indexed_questions : List (List (Int, Question))
    indexed_questions = 
      groups 
      |> List.map (List.indexedMap pair)

    indexed_groups : List ((Int, Int), Question)
    indexed_groups =
      indexed_questions
      |> List.indexedMap pair
      |> List.concatMap (\(gn, qs) -> List.map (\(qn,q) -> ((gn,qn),q)) qs)

  in
    indexed_groups
    |> List.concatMap (\((gn,qn),q) ->
      q.parts
      |> List.indexedMap pair
      |> List.concatMap (\(pn,part) -> ((gn,(qn,pn,Nothing)), part.info)::(List.indexedMap (\gapn gap -> ((gn,(qn,pn,Just gapn)),gap)) part.gaps))
    )

get_part : GroupPartPath -> Exam -> Maybe Part
get_part (gn,(qn,pn,mgn)) exam = 
  exam.question_groups
  |> LE.getAt gn
  |> Maybe.andThen (LE.getAt qn)
  |> Maybe.andThen (.parts >> LE.getAt pn)
  |> Maybe.andThen (\p -> case mgn of
       Nothing -> Just p
       Just gapn -> p.gaps |> LE.getAt gapn |> Maybe.map (\info -> {info = info, gaps = [], steps = []})
     )

one_after : a -> List a -> Maybe a
one_after x =
  LE.splitWhen ((==) x)
  >> Maybe.andThen (second >> List.drop 1 >> List.head)


prev_part : GroupPartPath -> Exam -> Maybe GroupPartPath
prev_part path =
  all_parts
  >> List.map first
  >> List.reverse
  >> one_after path

next_part : GroupPartPath -> Exam -> Maybe GroupPartPath
next_part path =
  all_parts
  >> List.map first
  >> one_after path

fromString : String -> Result NumbasExamError Exam
fromString str =
  case String.indices "\n" str of
    i::_ -> 
         str
      |> String.dropLeft i
      |> JD.decodeString decode
      |> Result.mapError JsonError
    [] -> Err <| FormatError "The header line seems to be missing"

get_question : QuestionPath -> Exam -> Maybe Question
get_question (gn,qn) =
  .question_groups
  >> LE.getAt gn
  >> Maybe.andThen (LE.getAt qn)

decode : JD.Decoder Exam
decode =
  JD.succeed Exam
  |> jam (JD.field "name" JD.string)
  |> jam (JD.field "question_groups" (JD.list decode_question_group))
  |> jam (JD.value)

decode_question_group : JD.Decoder (List Question)
decode_question_group = JD.field "questions" (JD.list decode_question)

decode_question : JD.Decoder Question
decode_question = 
  JD.succeed Question
  |> jam (JD.field "name" JD.string)
  |> jam (JD.field "parts" (JD.list decode_part))
  |> jam (JD.value)

decode_part : JD.Decoder Part
decode_part =
  JD.succeed Part
  |> jam decode_part_info
  |> jam (JD.oneOf [JD.field "gaps" (JD.list decode_part_info), JD.succeed []])
  |> jam (JD.oneOf [JD.field "steps" (JD.list decode_part_info), JD.succeed []])

decode_part_info : JD.Decoder PartInfo
decode_part_info =
  JD.succeed PartInfo
  |> jam (JD.field "type" JD.string)
  |> jam (JD.value)

part_type_names = Dict.fromList [
  ("information","Information only"),
  ("extension","Extension"),
  ("gapfill","Gap-fill"),
  ("jme","Mathematical expression"),
  ("numberentry","Number entry"),
  ("matrix","Matrix entry"),
  ("patternmatch","Match text pattern"),
  ("1_n_2","Choose one from a list"),
  ("m_n_2","Choose several from a list"),
  ("m_n_x","Match choices with answers")
  ]

short_part_label : GroupPartPath -> String
short_part_label (gn,(qn,pn,mgn)) =
  let
    gap = case mgn of
      Nothing -> ""
      Just gapn -> " gap "++(fi gapn)
  in
    (alpha pn) ++ ")" ++ gap

part_label : Exam -> GroupPartPath -> String
part_label exam ((gn,(qn,pn,mgn)) as path) =
  let
    mq = get_question (gn,qn) exam

    qname = mq |> Maybe.map (.name) |> Maybe.withDefault ("g"++(fi gn)++"q"++(fi qn))
  in
    qname ++ " " ++ (short_part_label path)
